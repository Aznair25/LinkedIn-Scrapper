from fastapi import APIRouter, HTTPException
from app.models.scrape_request import ScrapeRequest
from app.services.linkedin import (
    setup_driver,
    login_linkedin,
    scrape_profiles
)
import logging

logger = logging.getLogger(__name__)
router = APIRouter()

@router.post("/scrape-linkedin/")
def scrape_linkedin(request: ScrapeRequest):
    logger.info("Received scrape request.")
    driver = setup_driver()
    try:
        if not login_linkedin(driver, request.username, request.password):
            raise HTTPException(status_code=401, detail="LinkedIn login failed.")
        scrape_profiles(driver, request.search_url, request.max_pages)
        return {"message": "Scraping completed successfully."}
    finally:
        driver.quit()
        logger.info("Driver closed.")
