from app import db
from app.models import Task, DailyPlan, Document, ActivityLog, User
from app.interfaces import ITaskService, IPlanService, IDocumentService
from datetime import datetime, date
from flask import request


def _log(user_id, action, entity_type=None, entity_id=None, details=None):
    log = ActivityLog(
        user_id     = user_id,
        action      = action,
        entity_type = entity_type,
        entity_id   = entity_id,
        details     = details,
        ip_address  = request.remote_addr if request else None,
    )
    db.session.add(log)


# ── Task Service ─────────────────────────────────────────────────
class TaskService(ITaskService):

    def get_all(self, user_id: int, filters: dict):
        user = User.query.get(user_id)
        if user.is_admin():
            q = Task.query
        else:
            q = Task.query.filter(
                db.or_(Task.user_id == user_id, Task.assigned_to == user_id)
            )
        if filters.get('status'):
            q = q.filter_by(status=filters['status'])
        if filters.get('priority'):
            q = q.filter_by(priority=filters['priority'])
        if filters.get('category'):
            q = q.filter_by(category=filters['category'])
        if filters.get('q'):
            q = q.filter(Task.title.ilike(f"%{filters['q']}%"))
        return q.order_by(Task.created_at.desc()).all()

    def get_by_id(self, task_id: int, user_id: int):
        task = Task.query.get(task_id)
        if not task:
            return None
        user = User.query.get(user_id)
        if not user.is_admin() and task.user_id != user_id and task.assigned_to != user_id:
            return None
        return task

    def create(self, user_id: int, data: dict):
        try:
            task = Task(
                title       = data['title'],
                description = data.get('description'),
                priority    = data.get('priority', 'medium'),
                status      = data.get('status', 'todo'),
                category    = data.get('category'),
                assigned_to = data.get('assigned_to'),
                user_id     = user_id,
                due_date    = datetime.strptime(data['due_date'], '%Y-%m-%d').date() if data.get('due_date') else None,
            )
            db.session.add(task)
            db.session.flush()
            _log(user_id, f'Created task: {task.title}', 'task', task.id)
            db.session.commit()
            return task, None
        except Exception as e:
            db.session.rollback()
            return None, str(e)

    def update(self, task_id: int, user_id: int, data: dict):
        task = self.get_by_id(task_id, user_id)
        if not task:
            return None, 'Not found or unauthorized'
        try:
            for f in ('title', 'description', 'priority', 'status', 'category', 'assigned_to'):
                if f in data:
                    setattr(task, f, data[f])
            if 'due_date' in data:
                task.due_date = datetime.strptime(data['due_date'], '%Y-%m-%d').date() if data['due_date'] else None
            task.updated_at = datetime.utcnow()
            _log(user_id, f'Updated task: {task.title}', 'task', task.id, f'status={task.status}')
            db.session.commit()
            return task, None
        except Exception as e:
            db.session.rollback()
            return None, str(e)

    def delete(self, task_id: int, user_id: int):
        task = self.get_by_id(task_id, user_id)
        if not task:
            return False
        title = task.title
        db.session.delete(task)
        _log(user_id, f'Deleted task: {title}', 'task', task_id)
        db.session.commit()
        return True


# ── Plan Service ─────────────────────────────────────────────────
class PlanService(IPlanService):

    def get_by_date(self, user_id: int, date_str: str):
        try:
            d = datetime.strptime(date_str, '%Y-%m-%d').date()
        except Exception:
            d = date.today()
        return DailyPlan.query.filter_by(user_id=user_id, plan_date=d).order_by(DailyPlan.time_block).all()

    def create(self, user_id: int, data: dict):
        try:
            plan = DailyPlan(
                title       = data['title'],
                description = data.get('description'),
                time_block  = data.get('time_block'),
                plan_date   = datetime.strptime(data.get('plan_date', date.today().isoformat()), '%Y-%m-%d').date(),
                user_id     = user_id,
            )
            db.session.add(plan)
            db.session.flush()
            _log(user_id, f'Added plan: {plan.title}', 'plan', plan.id)
            db.session.commit()
            return plan, None
        except Exception as e:
            db.session.rollback()
            return None, str(e)

    def update(self, plan_id: int, user_id: int, data: dict):
        plan = DailyPlan.query.filter_by(id=plan_id, user_id=user_id).first()
        if not plan:
            return None, 'Not found'
        try:
            for f in ('title', 'description', 'time_block', 'completed'):
                if f in data:
                    setattr(plan, f, data[f])
            _log(user_id, f'Updated plan: {plan.title}', 'plan', plan.id)
            db.session.commit()
            return plan, None
        except Exception as e:
            db.session.rollback()
            return None, str(e)

    def delete(self, plan_id: int, user_id: int):
        plan = DailyPlan.query.filter_by(id=plan_id, user_id=user_id).first()
        if not plan:
            return False
        title = plan.title
        db.session.delete(plan)
        _log(user_id, f'Deleted plan: {title}', 'plan', plan_id)
        db.session.commit()
        return True


# ── Document Service ──────────────────────────────────────────────
class DocumentService(IDocumentService):

    def get_all(self, user_id: int, filters: dict):
        user = User.query.get(user_id)
        if user.is_admin():
            q = Document.query
        else:
            q = Document.query.filter(
                db.or_(Document.user_id == user_id, Document.is_shared == True)
            )
        if filters.get('doc_type'):
            q = q.filter_by(doc_type=filters['doc_type'])
        if filters.get('q'):
            q = q.filter(
                db.or_(Document.title.ilike(f"%{filters['q']}%"),
                       Document.content.ilike(f"%{filters['q']}%"))
            )
        return q.order_by(Document.updated_at.desc()).all()

    def get_by_id(self, doc_id: int, user_id: int):
        doc = Document.query.get(doc_id)
        if not doc:
            return None
        user = User.query.get(user_id)
        if not user.is_admin() and doc.user_id != user_id and not doc.is_shared:
            return None
        return doc

    def create(self, user_id: int, data: dict):
        try:
            doc = Document(
                title     = data['title'],
                content   = data.get('content'),
                doc_type  = data.get('doc_type', 'note'),
                tags      = data.get('tags'),
                is_shared = data.get('is_shared', False),
                user_id   = user_id,
            )
            db.session.add(doc)
            db.session.flush()
            _log(user_id, f'Created document: {doc.title}', 'document', doc.id)
            db.session.commit()
            return doc, None
        except Exception as e:
            db.session.rollback()
            return None, str(e)

    def update(self, doc_id: int, user_id: int, data: dict):
        doc = self.get_by_id(doc_id, user_id)
        if not doc:
            return None, 'Not found'
        try:
            for f in ('title', 'content', 'doc_type', 'tags', 'is_shared'):
                if f in data:
                    setattr(doc, f, data[f])
            doc.updated_at = datetime.utcnow()
            _log(user_id, f'Updated document: {doc.title}', 'document', doc.id)
            db.session.commit()
            return doc, None
        except Exception as e:
            db.session.rollback()
            return None, str(e)

    def delete(self, doc_id: int, user_id: int):
        doc = self.get_by_id(doc_id, user_id)
        if not doc:
            return False
        title = doc.title
        db.session.delete(doc)
        _log(user_id, f'Deleted document: {title}', 'document', doc_id)
        db.session.commit()
        return True
