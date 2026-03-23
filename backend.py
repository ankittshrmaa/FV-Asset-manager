from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, StreamingResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
import pandas as pd
from datetime import datetime
import os
import json
import fcntl
import io
from typing import List, Optional

app = FastAPI(title="Asset Manager API")

# Serve static files (frontend)
app.mount("/static", StaticFiles(directory="."), name="static")

# Enable CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

FILE = "data.xlsx"
LOCK_FILE = "data.xlsx.lock"

# Column order for Excel
COLUMNS = [
    "asset_id", "timestamp", "employee_name", "department", "hostname",
    "device_type", "processor", "ram", "disk", "antivirus_installed",
    "laptop_brand", "laptop_sn",
    "monitor_1_brand", "monitor_1_sn", "monitor_2_brand", "monitor_2_sn",
    "keyboard_brand", "keyboard_sn",
    "mouse_brand", "mouse_sn",
    "headphone_brand", "headphone_sn",
    "webcam_brand", "webcam_sn",
    "notes"
]


def get_next_seq(department: str) -> int:
    """Get next sequence number for department."""
    if not os.path.exists(FILE):
        return 1
    
    try:
        df = pd.read_excel(FILE)
        if df.empty or "department" not in df.columns:
            return 1
        
        dept_assets = df[df["department"] == department.upper()]
        if dept_assets.empty:
            return 1
        
        # Extract sequence from asset_id (format: FSPL-DEPT-XXX)
        # Handle both old format (hex) and new format (FSPL-DEPT-XXX)
        valid_ids = dept_assets["asset_id"].str.match(r"^FSPL-[A-Z]+-\d+$", na=False)
        if not valid_ids.any():
            return 1
        
        dept_assets = dept_assets[valid_ids]
        seqs = dept_assets["asset_id"].str.extract(r"-(\d+)$")[0].astype(float)
        seqs = seqs.dropna()
        if seqs.empty:
            return 1
        return int(seqs.max()) + 1
    except Exception:
        return 1


def save_to_excel(row: dict):
    """Thread-safe Excel save with file locking."""
    # Create lock file for atomic operations
    lock_fd = open(LOCK_FILE, 'w')
    try:
        fcntl.flock(lock_fd.fileno(), fcntl.LOCK_EX)
        
        df_new = pd.DataFrame([row])
        
        if os.path.exists(FILE):
            df_old = pd.read_excel(FILE)
            # Ensure columns match
            for col in COLUMNS:
                if col not in df_old.columns:
                    df_old[col] = ""
            df = pd.concat([df_old, df_new], ignore_index=True)
        else:
            df = df_new
        
        # Reorder columns
        existing_cols = [c for c in COLUMNS if c in df.columns]
        df = df[existing_cols]
        
        df.to_excel(FILE, index=False)
    finally:
        fcntl.flock(lock_fd.fileno(), fcntl.LOCK_UN)
        lock_fd.close()


def parse_form_to_row(form, seq: int) -> dict:
    """Parse form data to row dict."""
    department = form.get("department", "").upper()
    asset_id = f"FSPL-{department}-{seq:03d}"
    
    # Parse monitors
    monitors_brand = form.getlist("monitor_brand[]")
    monitors_sn = form.getlist("monitor_sn[]")
    
    row = {
        "asset_id": asset_id,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "employee_name": form.get("name", ""),
        "department": department,
        "hostname": form.get("hostname", ""),
        "device_type": form.get("device_type", ""),
        "processor": form.get("processor", ""),
        "ram": form.get("ram", ""),
        "disk": form.get("disk", ""),
        "antivirus_installed": form.get("antivirus_installed", ""),
        
        # Laptop fields
        "laptop_brand": form.get("laptop_brand", ""),
        "laptop_sn": form.get("laptop_sn", ""),
        
        # Monitor fields (up to 2)
        "monitor_1_brand": monitors_brand[0] if len(monitors_brand) > 0 else "",
        "monitor_1_sn": monitors_sn[0] if len(monitors_sn) > 0 else "",
        "monitor_2_brand": monitors_brand[1] if len(monitors_brand) > 1 else "",
        "monitor_2_sn": monitors_sn[1] if len(monitors_sn) > 1 else "",
        
        # Peripherals
        "keyboard_brand": form.get("keyboard_brand", ""),
        "keyboard_sn": form.get("keyboard_sn", ""),
        "mouse_brand": form.get("mouse_brand", ""),
        "mouse_sn": form.get("mouse_sn", ""),
        "headphone_brand": form.get("headphone_brand", ""),
        "headphone_sn": form.get("headphone_sn", ""),
        "webcam_brand": form.get("webcam_brand", ""),
        "webcam_sn": form.get("webcam_sn", ""),
        
        "notes": form.get("notes", "")
    }
    
    return row


@app.post("/submit")
async def submit(request: Request):
    """Submit single asset."""
    try:
        form = await request.form()
        department = form.get("department", "").upper()
        
        if not department:
            return JSONResponse(
                {"status": "error", "message": "Department is required"},
                status_code=400
            )
        
        seq = get_next_seq(department)
        row = parse_form_to_row(form, seq)
        save_to_excel(row)
        
        return {"status": "saved", "asset_id": row["asset_id"]}
    except Exception as e:
        return JSONResponse(
            {"status": "error", "message": str(e)},
            status_code=500
        )


@app.post("/submit-batch")
async def submit_batch(request: Request):
    """Submit multiple assets at once."""
    try:
        form = await request.form()
        
        # Get number of assets in batch
        count = int(form.get("batch_count", 1))
        department = form.get("department", "").upper()
        
        if not department:
            return JSONResponse(
                {"status": "error", "message": "Department is required"},
                status_code=400
            )
        
        saved_ids = []
        seq = get_next_seq(department)
        
        for i in range(count):
            # Build form data for each asset
            row_data = {}
            row_data["name"] = form.get(f"items[{i}][name]", "")
            row_data["department"] = department
            row_data["hostname"] = form.get(f"items[{i}][hostname]", "")
            row_data["device_type"] = form.get(f"items[{i}][device_type]", "")
            row_data["processor"] = form.get(f"items[{i}][processor]", "")
            row_data["ram"] = form.get(f"items[{i}][ram]", "")
            row_data["disk"] = form.get(f"items[{i}][disk]", "")
            row_data["antivirus_installed"] = form.get(f"items[{i}][antivirus_installed]", "")
            row_data["laptop_brand"] = form.get(f"items[{i}][laptop_brand]", "")
            row_data["laptop_sn"] = form.get(f"items[{i}][laptop_sn]", "")
            row_data["keyboard_brand"] = form.get(f"items[{i}][keyboard_brand]", "")
            row_data["keyboard_sn"] = form.get(f"items[{i}][keyboard_sn]", "")
            row_data["mouse_brand"] = form.get(f"items[{i}][mouse_brand]", "")
            row_data["mouse_sn"] = form.get(f"items[{i}][mouse_sn]", "")
            row_data["headphone_brand"] = form.get(f"items[{i}][headphone_brand]", "")
            row_data["headphone_sn"] = form.get(f"items[{i}][headphone_sn]", "")
            row_data["webcam_brand"] = form.get(f"items[{i}][webcam_brand]", "")
            row_data["webcam_sn"] = form.get(f"items[{i}][webcam_sn]", "")
            row_data["notes"] = form.get(f"items[{i}][notes]", "")
            
            # Monitors
            row_data["monitor_brand[]"] = form.getlist(f"items[{i}][monitor_brand][]")
            row_data["monitor_sn[]"] = form.getlist(f"items[{i}][monitor_sn][]")
            
            # Create a mock-like object for parse_form_to_row
            class MockForm(dict):
                def get(self, key, default=""):
                    return super().get(key, default)
                def getlist(self, key):
                    val = self.get(key, [])
                    return val if isinstance(val, list) else [val]
            
            mock_form = MockForm(row_data)
            row = parse_form_to_row(mock_form, seq + i)
            save_to_excel(row)
            saved_ids.append(row["asset_id"])
        
        return {
            "status": "saved",
            "count": len(saved_ids),
            "asset_ids": saved_ids
        }
    except Exception as e:
        return JSONResponse(
            {"status": "error", "message": str(e)},
            status_code=500
        )


def clean_df_for_json(df: pd.DataFrame) -> List[dict]:
    """Clean DataFrame for JSON serialization (handle NaN values)."""
    # Replace NaN with None
    df = df.replace({pd.NA: None, float('nan'): None})
    # Convert to dict
    return df.where(pd.notnull(df), None).to_dict(orient="records")


@app.get("/assets")
async def get_assets(
    department: Optional[str] = None,
    hostname: Optional[str] = None,
    format: str = "json"
):
    """Query assets with optional filters."""
    try:
        if not os.path.exists(FILE):
            return {"status": "success", "data": [], "count": 0}
        
        df = pd.read_excel(FILE)
        
        # Apply filters
        if department:
            df = df[df["department"] == department.upper()]
        if hostname:
            df = df[df["hostname"].str.contains(hostname, case=False, na=False)]
        
        if format == "excel":
            output = io.BytesIO()
            df.to_excel(output, index=False)
            output.seek(0)
            return StreamingResponse(
                output,
                media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                headers={"Content-Disposition": "attachment; filename=assets.xlsx"}
            )
        
        return {
            "status": "success",
            "data": clean_df_for_json(df),
            "count": len(df)
        }
    except Exception as e:
        return JSONResponse(
            {"status": "error", "message": str(e)},
            status_code=500
        )


@app.get("/stats")
async def get_stats():
    """Get summary statistics."""
    try:
        if not os.path.exists(FILE):
            return {"status": "success", "total": 0}
        
        df = pd.read_excel(FILE)
        
        return {
            "status": "success",
            "total": len(df),
            "by_department": df["department"].value_counts().to_dict() if "department" in df.columns else {},
            "by_device_type": df["device_type"].value_counts().to_dict() if "device_type" in df.columns else {}
        }
    except Exception as e:
        return JSONResponse(
            {"status": "error", "message": str(e)},
            status_code=500
        )


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "ok", "timestamp": datetime.now().isoformat()}
