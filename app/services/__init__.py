from app.services.data_services import TaskService, PlanService, DocumentService
from app.services.auth_service  import AuthService
from app.services.user_service  import UserService
from app.services.ai_service    import AIService
from app.services.settings_service import settings_service

task_service     = TaskService()
plan_service     = PlanService()
doc_service      = DocumentService()
auth_service     = AuthService()
user_service     = UserService()
ai_service       = AIService()
