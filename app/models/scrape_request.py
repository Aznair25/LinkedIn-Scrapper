from pydantic import BaseModel

class ScrapeRequest(BaseModel):
    username: str
    password: str
    search_url: str
    max_pages: int | None = None