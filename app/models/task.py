from app import db
from datetime import datetime


class Task(db.Model):
    __tablename__ = 'tasks'

    id          = db.Column(db.Integer, primary_key=True)
    title       = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    priority    = db.Column(db.String(20), default='medium')
    status      = db.Column(db.String(20), default='todo')
    category    = db.Column(db.String(50))
    due_date    = db.Column(db.Date)
    user_id     = db.Column(db.Integer, db.ForeignKey('users.id'))
    assigned_to = db.Column(db.Integer, db.ForeignKey('users.id'))
    created_at  = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at  = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # ── Recurring task support ─────────────────────────────────────
    # recur_type: None | 'daily' | 'weekly' | 'monthly'
    # recur_day:  for weekly = 0-6 (Mon-Sun); for monthly = 1-31
    recur_type  = db.Column(db.String(20), nullable=True)
    recur_day   = db.Column(db.Integer,    nullable=True)

    def to_dict(self):
        return {
            'id':          self.id,
            'title':       self.title,
            'description': self.description or '',
            'priority':    self.priority,
            'status':      self.status,
            'category':    self.category or '',
            'due_date':    self.due_date.isoformat() if self.due_date else '',
            'user_id':     self.user_id,
            'assigned_to': self.assigned_to,
            'recur_type':  self.recur_type or '',
            'recur_day':   self.recur_day,
        }


class DailyPlan(db.Model):
    __tablename__ = 'daily_plans'
    id            = db.Column(db.Integer, primary_key=True)
    plan_date     = db.Column(db.Date, nullable=False, default=datetime.utcnow().date)
    title         = db.Column(db.String(200), nullable=False)
    description   = db.Column(db.Text)
    time_block    = db.Column(db.String(50))
    completed     = db.Column(db.Boolean, default=False)
    user_id       = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    created_at    = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id':          self.id,
            'plan_date':   self.plan_date.isoformat(),
            'title':       self.title,
            'description': self.description,
            'time_block':  self.time_block,
            'completed':   self.completed,
            'user_id':     self.user_id,
            'created_at':  self.created_at.isoformat(),
        }


class Document(db.Model):
    __tablename__ = 'documents'
    id            = db.Column(db.Integer, primary_key=True)
    title         = db.Column(db.String(200), nullable=False)
    content       = db.Column(db.Text)
    doc_type      = db.Column(db.String(50), default='note')   # note / report / meeting / decision / policy
    tags          = db.Column(db.String(300))
    is_shared     = db.Column(db.Boolean, default=False)
    user_id       = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    created_at    = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at    = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self):
        return {
            'id':         self.id,
            'title':      self.title,
            'content':    self.content,
            'doc_type':   self.doc_type,
            'tags':       self.tags,
            'is_shared':  self.is_shared,
            'user_id':    self.user_id,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat(),
        }


class ActivityLog(db.Model):
    __tablename__ = 'activity_logs'
    id            = db.Column(db.Integer, primary_key=True)
    action        = db.Column(db.String(200), nullable=False)
    entity_type   = db.Column(db.String(50))
    entity_id     = db.Column(db.Integer)
    details       = db.Column(db.Text)
    ip_address    = db.Column(db.String(45))
    user_id       = db.Column(db.Integer, db.ForeignKey('users.id'))
    created_at    = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id':          self.id,
            'action':      self.action,
            'entity_type': self.entity_type,
            'entity_id':   self.entity_id,
            'details':     self.details,
            'user_id':     self.user_id,
            'created_at':  self.created_at.isoformat(),
        }
