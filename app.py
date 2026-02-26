import os
import json
import threading
import logging
from fastapi import FastAPI, BackgroundTasks, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel
import uvicorn
import time
import random
from typing import List, Optional

# Import existing bot
from facebook_bot import FacebookBot, BASE_DIR

app = FastAPI(title="Facebook Bot GUI")

# Global ref to bot thread
bot_thread = None
bot_instance = None
is_running = False

class Config(BaseModel):
    email: str
    password: str
    group_url: Optional[str] = "" 
    group_urls: List[str] = []
    page_url: Optional[str] = ""
    post_content: Optional[str] = ""
    min_delay: int = 1
    max_delay: int = 3
    # New settings
    between_groups_min: int = 60
    between_groups_max: int = 180
    loop_rest_min: int = 3600
    loop_rest_max: int = 7200

def run_bot_task():
    global is_running, bot_instance
    is_running = True
    
    while is_running:
        try:
            logging.info("--- STARTING NEW FULL CYCLE ---")
            bot_instance = FacebookBot()
            bot_instance.run(is_gui=True)
            
            # One pass completed. Now rest before next cycle.
            if not is_running: break
            
            # Use current config for rest interval
            config_data = bot_instance.config
            rest_min = config_data.get('loop_rest_min', 3600)
            rest_max = config_data.get('loop_rest_max', 7200)
            
            rest_time = random.uniform(rest_min, rest_max)
            logging.info(f"Cycle finished. Resting for {rest_time/60:.1f} minutes before next run...")
            
            # Sleep in chunks to allow fast stop
            start_rest = time.time()
            while time.time() - start_rest < rest_time:
                if not is_running: break
                time.sleep(1)
                
        except Exception as e:
            logging.error(f"FATAL: Bot crashed during run: {e}. Restarting in 60s...")
            if not is_running: break
            time.sleep(60)
            
    logging.info("Background bot task terminated.")
    is_running = False

@app.get("/", response_class=HTMLResponse)
async def index():
    with open(os.path.join(BASE_DIR, "static/index.html"), "r", encoding="utf-8") as f:
        return f.read()

@app.get("/api/config")
async def get_config():
    config_path = os.path.join(BASE_DIR, "config.json")
    if os.path.exists(config_path):
        with open(config_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

@app.post("/api/config")
async def save_config(config: Config):
    config_path = os.path.join(BASE_DIR, "config.json")
    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(config.dict(), f, indent=4, ensure_ascii=False)
    return {"status": "success"}

@app.get("/api/status")
async def get_status():
    pic_dir = os.path.join(BASE_DIR, "pic")
    img_count = 0
    if os.path.exists(pic_dir):
        img_count = len([f for f in os.listdir(pic_dir) if f.lower().endswith(('.png', '.jpg', '.jpeg'))])
    
    return {
        "running": is_running,
        "image_count": img_count
    }

@app.post("/api/start")
async def start_bot(background_tasks: BackgroundTasks):
    global bot_thread, is_running
    if is_running:
        return {"status": "already running"}
    
    background_tasks.add_task(run_bot_task)
    return {"status": "started"}

@app.post("/api/stop")
async def stop_bot():
    global bot_instance, is_running
    if not is_running:
        return {"status": "not running"}
    
    # Simple stop: quit driver if exists
    if bot_instance and hasattr(bot_instance, 'driver'):
        try:
            bot_instance.driver.quit()
        except:
            pass
    is_running = False
    return {"status": "stopping"}

@app.get("/api/logs")
async def get_logs():
    log_path = os.path.join(BASE_DIR, "facebook_bot.log")
    if os.path.exists(log_path):
        with open(log_path, "r", encoding="utf-8") as f:
            # Read last 100 lines
            lines = f.readlines()
            return {"logs": "".join(lines[-100:])}
    return {"logs": "No logs found."}

# Mount static files
app.mount("/static", StaticFiles(directory=os.path.join(BASE_DIR, "static")), name="static")

if __name__ == "__main__":
    print(f"Server starting at http://localhost:8000")
    uvicorn.run(app, host="0.0.0.0", port=8000)
