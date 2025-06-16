from fastapi import FastAPI
from app.routes.scrape import router as scrape_router

app = FastAPI()
app.include_router(scrape_router)

@app.get("/")
def root():
    return {"message": "LinkedIn Scraper API is live."}
