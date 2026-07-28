"""Import all models so Alembic autogenerate + relationships resolve."""
from app.models.lookup import Activity, Agency, Company, Region, TenderType
from app.models.saas import (
    BidProposal, KnowledgeChunk, KnowledgeDocument, Organization, SavedSearch, User,
)
from app.models.tender import Award, AwardWinner, Tender, TenderBid

__all__ = [
    "Region", "Agency", "Activity", "TenderType", "Company",
    "Tender", "Award", "AwardWinner", "TenderBid",
    "Organization", "User", "KnowledgeDocument", "KnowledgeChunk", "BidProposal",
    "SavedSearch",
]
