# Import all models to register them with the declarative Base
from app.models.user import User
from app.models.product import Product, ProductionBatch, Facility, ProductionLine
from app.models.complaint import Complaint, ComplaintAttachment, ComplaintStatusHistory
from app.models.investigation import Investigation
from app.models.corrective_action import CorrectiveAction
from app.models.notification import CustomerProfile, ModelPrediction, Notification, AuditLog

__all__ = [
    "User",
    "Product",
    "ProductionBatch",
    "Facility",
    "ProductionLine",
    "Complaint",
    "ComplaintAttachment",
    "ComplaintStatusHistory",
    "Investigation",
    "CorrectiveAction",
    "CustomerProfile",
    "ModelPrediction",
    "Notification",
    "AuditLog",
]
