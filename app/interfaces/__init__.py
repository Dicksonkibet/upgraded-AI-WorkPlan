"""
Interfaces (abstract contracts) for all services.
Depend on these, not on concrete implementations.
"""
from abc import ABC, abstractmethod
from typing import Optional, List


class IAuthService(ABC):
    @abstractmethod
    def register(self, data: dict) -> tuple: ...

    @abstractmethod
    def login(self, email: str, password: str) -> tuple: ...

    @abstractmethod
    def send_reset_email(self, email: str) -> bool: ...

    @abstractmethod
    def reset_password(self, token: str, new_password: str) -> bool: ...

    @abstractmethod
    def verify_email(self, token: str) -> bool: ...


class IUserService(ABC):
    @abstractmethod
    def get_all(self, page: int, filters: dict) -> tuple: ...

    @abstractmethod
    def get_by_id(self, user_id: int): ...

    @abstractmethod
    def update(self, user_id: int, data: dict) -> tuple: ...

    @abstractmethod
    def delete(self, user_id: int) -> bool: ...

    @abstractmethod
    def toggle_active(self, user_id: int) -> bool: ...

    @abstractmethod
    def change_role(self, user_id: int, role_id: int) -> bool: ...


class ITaskService(ABC):
    @abstractmethod
    def get_all(self, user_id: int, filters: dict) -> List: ...

    @abstractmethod
    def get_by_id(self, task_id: int, user_id: int): ...

    @abstractmethod
    def create(self, user_id: int, data: dict) -> tuple: ...

    @abstractmethod
    def update(self, task_id: int, user_id: int, data: dict) -> tuple: ...

    @abstractmethod
    def delete(self, task_id: int, user_id: int) -> bool: ...


class IPlanService(ABC):
    @abstractmethod
    def get_by_date(self, user_id: int, date: str) -> List: ...

    @abstractmethod
    def create(self, user_id: int, data: dict) -> tuple: ...

    @abstractmethod
    def update(self, plan_id: int, user_id: int, data: dict) -> tuple: ...

    @abstractmethod
    def delete(self, plan_id: int, user_id: int) -> bool: ...


class IDocumentService(ABC):
    @abstractmethod
    def get_all(self, user_id: int, filters: dict) -> List: ...

    @abstractmethod
    def get_by_id(self, doc_id: int, user_id: int): ...

    @abstractmethod
    def create(self, user_id: int, data: dict) -> tuple: ...

    @abstractmethod
    def update(self, doc_id: int, user_id: int, data: dict) -> tuple: ...

    @abstractmethod
    def delete(self, doc_id: int, user_id: int) -> bool: ...


class IAIService(ABC):
    @abstractmethod
    def chat(self, user_id: int, messages: List[dict], context: dict) -> str: ...

    @abstractmethod
    def summarize_tasks(self, user_id: int) -> str: ...

    @abstractmethod
    def suggest_plan(self, user_id: int, date: str) -> str: ...
