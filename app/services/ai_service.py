import json
import re
from groq import Groq
from app.interfaces import IAIService
from app.models import Task, DailyPlan, Document, ActivityLog
from flask import current_app
from datetime import date, datetime, timedelta


class AIService(IAIService):

    # ── Pro Trial: first 20 task-creation actions are free ────────────
    PRO_TRIAL_LIMIT = 20

    def get_trial_usage(self, user) -> int:
        """Count how many AI task-creation actions the user has used in trial."""
        from app.models.subscription import AIUsage
        row = AIUsage.query.filter_by(user_id=user.id, date=date(2000, 1, 1)).first()
        return row.msg_count if row else 0

    def increment_trial_usage(self, user):
        """Track trial task creations using a sentinel date (2000-01-01)."""
        from app.models.subscription import AIUsage
        from app import db
        sentinel = date(2000, 1, 1)
        row = AIUsage.query.filter_by(user_id=user.id, date=sentinel).first()
        if not row:
            row = AIUsage(user_id=user.id, date=sentinel, msg_count=0)
            db.session.add(row)
        row.msg_count += 1
        db.session.commit()

    def trial_tasks_remaining(self, user) -> int:
        if user.is_pro:
            return None  # unlimited
        used = self.get_trial_usage(user)
        return max(0, self.PRO_TRIAL_LIMIT - used)

    # ── System Prompt ─────────────────────────────────────────────────
    def _system_prompt(self, user, context: dict = None, service: str = None):
        limits  = user.get_limits()
        usage   = user.get_usage()
        plan    = 'Pro ⚡' if user.is_pro else 'Free'
        trial_remaining = self.trial_tasks_remaining(user)

        # Permissions
        perms = []
        if user.has_permission('tasks.create'):   perms.append('create_task')
        if user.has_permission('tasks.edit'):     perms.append('update_task')
        if user.has_permission('tasks.delete'):   perms.append('delete_task')
        if user.has_permission('planner.create'): perms.append('create_plan')
        if user.has_permission('planner.edit'):   perms.append('update_plan')
        if user.has_permission('docs.create'):    perms.append('create_doc')
        if user.has_permission('docs.edit'):      perms.append('update_doc')

        # AI config from admin settings
        ai_persona  = self._get_ai_config('ai_persona_name',  'WorkPro AI Agent')
        ai_tone     = self._get_ai_config('ai_response_tone', 'professional')
        ai_intro    = self._get_ai_config('ai_intro_message', '')

        # Trial or pro note
        trial_note = ''
        if not user.is_pro:
            if trial_remaining > 0:
                trial_note = f'\n- NEW USER PRO TRIAL: {trial_remaining}/{self.PRO_TRIAL_LIMIT} free task actions remaining. Mention this when creating tasks.'
            else:
                trial_note = f'\n- FREE PLAN: Trial expired. Task creation/updates are locked. Encourage upgrading to Pro. AI messages remaining today: {(limits["ai_msgs"] or 5) - usage["ai_msgs"]}.'

        # Action capability
        can_act = user.is_pro or trial_remaining > 0
        if can_act and perms:
            action_instructions = f"""

When the user wants to CREATE, UPDATE, or DELETE data, respond with a JSON action block EXACTLY like this:
```action
{{"action": "create_task", "data": {{"title": "...", "priority": "high|medium|low", "status": "todo", "description": "...", "due_date": "YYYY-MM-DD"}}}}
```
Available actions: {', '.join(perms)}

Action schemas:
- create_task: {{"title": str, "description": str?, "priority": "high|medium|low", "status": "todo", "category": str?, "due_date": "YYYY-MM-DD"?}}
- update_task: {{"id": int, "title": str?, "status": "todo|in_progress|done"?, "priority": str?}}
- delete_task: {{"id": int}}  ← ALWAYS ask for confirmation first, never delete without explicit user confirmation
- create_plan: {{"title": str, "description": str?, "time_block": "HH:MM-HH:MM"?, "plan_date": "YYYY-MM-DD"?}}
- update_plan: {{"id": int, "completed": bool?, "title": str?}}
- create_doc: {{"title": str, "content": str, "doc_type": "note|report|meeting|decision|policy"}}
- update_doc: {{"id": int, "title": str?, "content": str?}}

RULES: 
- For delete actions, ALWAYS explain what will be deleted and ask "Please type 'confirm' to proceed" before outputting the action block.
- After a successful action, show a brief, warm success message.
- If an action fails, explain clearly what went wrong and how to fix it."""
        else:
            action_instructions = '\nYou are in READ-ONLY mode for data actions. You can still answer questions, explain the system, and provide analysis. Gently suggest upgrading to Pro for full management capabilities.'

        # Service-specific hint
        svc_hint = ''
        if service:
            svc_hints = {
                'task_create': 'The user is using the Task Creation service. Guide them through creating a task. Extract all details from their message.',
                'task_update': 'The user is using the Task Update service. Help them update an existing task by ID.',
                'task_delete': 'The user is using the Task Delete service. ALWAYS confirm before deleting.',
                'plan_day':    'The user is using the Daily Planner service. Create a detailed schedule with time blocks.',
                'doc_create':  'The user is using the Document Creation service. Generate a professional, well-structured document.',
                'generate_report': 'The user wants a detailed AI report. Use ALL available data. Generate sections with headers, metrics, percentages, and specific recommendations. Be thorough and professional.',
                'task_summary': 'The user wants a task summary. List items clearly, identify priorities, flag overdue items.',
                'system_explain': 'The user wants to learn about WorkPro. Be a friendly guide. Explain features clearly with examples.',
                'free_chat':   'The user is in free chat mode. Be helpful and versatile.',
            }
            svc_hint = f'\n\nACTIVE SERVICE: {svc_hints.get(service, "")}'

        # Build context string
        ctx_str = ''
        if context:
            ctx_str = '\n\nLIVE WORKSPACE DATA:'
            if context.get('tasks'):
                ctx_str += '\n\nTasks:\n' + '\n'.join(
                    f'  [{t["id"]}] {t["title"]} — {t["status"]} ({t["priority"]} priority)' +
                    (f', due {t["due_date"]}' if t.get("due_date") else '') +
                    (f', category: {t["category"]}' if t.get("category") else '')
                    for t in context['tasks']
                )
            if context.get('today_plans'):
                ctx_str += '\n\nToday\'s Plans:\n' + '\n'.join(
                    f'  [{p["id"]}] {p["time_block"] or "?"} {p["title"]} {"✓" if p["completed"] else "○"}'
                    for p in context['today_plans']
                )
            if context.get('docs'):
                ctx_str += '\n\nRecent Documents:\n' + '\n'.join(
                    f'  [{d["id"]}] {d["title"]} ({d["doc_type"]})'
                    for d in context['docs'][:5]
                )
            if context.get('stats'):
                s = context['stats']
                ctx_str += f'\n\nStats: {s.get("total_tasks",0)} total tasks, {s.get("done_tasks",0)} completed, {s.get("overdue_tasks",0)} overdue, {s.get("total_docs",0)} documents'

        system = (
            f"You are {ai_persona}, an intelligent AI agent with full access to the WorkPro productivity management system.\n"
            f"User: {user.full_name} | Plan: {plan} | Role: {user.role.name if user.role else 'user'}\n"
            f"Today: {date.today().strftime('%A, %B %d, %Y')}\n"
            f"Permissions: {', '.join(perms) if perms else 'read-only'}{trial_note}"
            f"{action_instructions}"
            f"{svc_hint}"
            f"{ctx_str}\n\n"
            f"Tone: {ai_tone}. Be concise, warm, and actionable. After completing actions, always offer what to do next.\n"
        )
        if ai_intro:
            system += f"Custom intro for new sessions: {ai_intro}\n"

        return system

    def _get_ai_config(self, key, default=''):
        """Get AI config from admin settings, fall back to default."""
        try:
            from app.models.settings import SystemSetting
            row = SystemSetting.query.filter_by(key=key).first()
            return row.value if (row and row.value) else default
        except Exception:
            return default

    def _build_context(self, user) -> dict:
        from sqlalchemy import func
        today = date.today()
        tasks = Task.query.filter_by(user_id=user.id).all()
        done_count    = sum(1 for t in tasks if t.status == 'done')
        overdue_count = sum(1 for t in tasks if t.due_date and t.due_date < today and t.status != 'done')
        return {
            'tasks': [t.to_dict() for t in sorted(tasks, key=lambda x: x.created_at, reverse=True)[:20]],
            'today_plans': [p.to_dict() for p in DailyPlan.query.filter_by(
                user_id=user.id, plan_date=today).all()],
            'docs': [d.to_dict() for d in Document.query.filter_by(
                user_id=user.id).order_by(Document.updated_at.desc()).limit(10).all()],
            'stats': {
                'total_tasks':   len(tasks),
                'done_tasks':    done_count,
                'overdue_tasks': overdue_count,
                'total_docs':    Document.query.filter_by(user_id=user.id).count(),
            }
        }

    # ── Deterministic report metrics ────────────────────────────────────
    # NOTE: numbers are computed here in Python, not by the LLM. Small/fast
    # models (the default is llama-3.1-8b-instant) are unreliable at counting
    # and cross-checking buckets like "overdue / due today / upcoming" against
    # a task list — that's how you get reports where the categories don't add
    # up to the total. The AI is only ever asked to narrate numbers we hand it.
    def compute_metrics(self, user) -> dict:
        today    = date.today()
        week_end = today + timedelta(days=7)
        tasks    = Task.query.filter_by(user_id=user.id).all()
        total    = len(tasks)

        done        = [t for t in tasks if t.status == 'done']
        in_progress = [t for t in tasks if t.status == 'in_progress']
        todo        = [t for t in tasks if t.status == 'todo']
        overdue     = [t for t in tasks if t.due_date and t.due_date < today and t.status != 'done']
        due_today   = [t for t in tasks if t.due_date == today and t.status != 'done']
        upcoming    = [t for t in tasks if t.due_date and today < t.due_date <= week_end and t.status != 'done']

        def pct(n):
            return round((n / total) * 100, 1) if total else 0.0

        priority_counts = {'high': 0, 'medium': 0, 'low': 0}
        category_counts = {}
        for t in tasks:
            if t.priority in priority_counts:
                priority_counts[t.priority] += 1
            cat = t.category or 'Uncategorized'
            category_counts[cat] = category_counts.get(cat, 0) + 1

        return {
            'generated_at':     today.isoformat(),
            'total_tasks':      total,
            'completed_tasks':  len(done),
            'completed_pct':    pct(len(done)),
            'in_progress':      len(in_progress),
            'in_progress_pct':  pct(len(in_progress)),
            'todo':             len(todo),
            'todo_pct':         pct(len(todo)),
            'overdue_tasks':    len(overdue),
            'overdue_pct':      pct(len(overdue)),
            'due_today':        len(due_today),
            'upcoming_tasks':   len(upcoming),
            'priority_counts':  priority_counts,
            'priority_pct':     {k: pct(v) for k, v in priority_counts.items()},
            'category_counts':  category_counts,
            'overdue_items':    [t.to_dict() for t in overdue],
            'due_today_items':  [t.to_dict() for t in due_today],
        }

    def generate_report(self, user, report_type: str = 'productivity') -> dict:
        """Returns {'metrics': <exact numbers>, 'narrative': <AI-written summary+recommendations>}.
        The frontend renders metrics straight from this dict (guaranteed correct) and
        only runs the narrative text through markdown rendering."""
        m = self.compute_metrics(user)

        facts = (
            "VERIFIED METRICS (already calculated correctly — do NOT recalculate, "
            "restate as a table, or invent additional numbers; just refer to them in prose):\n"
            f"- Total tasks: {m['total_tasks']}\n"
            f"- Completed: {m['completed_tasks']} ({m['completed_pct']}%)\n"
            f"- In progress: {m['in_progress']} ({m['in_progress_pct']}%)\n"
            f"- To do: {m['todo']} ({m['todo_pct']}%)\n"
            f"- Overdue: {m['overdue_tasks']} ({m['overdue_pct']}%)\n"
            f"- Due today: {m['due_today']}\n"
            f"- Due in next 7 days: {m['upcoming_tasks']}\n"
            f"- Priority split — High: {m['priority_counts']['high']}, "
            f"Medium: {m['priority_counts']['medium']}, Low: {m['priority_counts']['low']}\n"
        )

        prompts = {
            'productivity': "Write a short productivity narrative: a 2-3 sentence executive summary, "
                             "then 3 specific, personalized recommendations as a bullet list, referencing the overdue/due-today items by name where useful.",
            'status':       "Write a weekly status update suitable for sharing with management: what got done, "
                             "what's in progress, what's blocked, and a one-line plan for next week. Reference task titles, not just counts.",
            'performance':  "Write a performance analysis: call out what's going well, what's at risk (especially "
                             "overdue high-priority items), and one concrete action plan with a timeframe.",
        }
        instruction = (
            f"{facts}\n{prompts.get(report_type, prompts['productivity'])}\n\n"
            "Do not output a metrics table or repeat the numbers list above verbatim — that part is already "
            "rendered for the user. Just write the narrative and recommendations in plain prose/bullets."
        )

        # Reports lean on cross-referencing numbers and items, so use the
        # strongest configured model rather than the fast default chat model.
        narrative = self.chat(
            user,
            [{'role': 'user', 'content': instruction}],
            service='generate_report',
            model_override=self._get_ai_config('ai_report_model', 'llama-3.3-70b-versatile'),
        )
        return {'metrics': m, 'narrative': narrative, 'report_type': report_type}

    def parse_action(self, reply: str):
        match = re.search(r'```action\s*([\s\S]+?)```', reply)
        if not match:
            return None, reply
        try:
            action_data = json.loads(match.group(1).strip())
            clean_reply = re.sub(r'```action[\s\S]+?```', '', reply).strip()
            return action_data, clean_reply
        except Exception:
            return None, reply

    def execute_action(self, user, action_data: dict):
        from app.services import task_service, plan_service, doc_service
        action = action_data.get('action')
        data   = action_data.get('data', {})
        result = {'action': action, 'success': False, 'message': ''}

        try:
            if action == 'create_task':
                if not user.is_pro:
                    remaining = self.trial_tasks_remaining(user)
                    if remaining <= 0:
                        result['message'] = '🔒 Your free trial (20 tasks) has been used. Upgrade to Pro for unlimited task creation.'
                        return result
                task, err = task_service.create(user.id, data)
                if task:
                    if not user.is_pro:
                        self.increment_trial_usage(user)
                    result['success'] = True
                    result['message'] = f'✅ Task "{task.title}" created successfully!'
                    result['item'] = task.to_dict()
                else:
                    result['message'] = err or 'Failed to create task.'

            elif action == 'update_task':
                task, err = task_service.update(data.get('id'), user.id, data)
                if task:
                    result['success'] = True
                    result['message'] = f'✅ Task "{task.title}" updated successfully!'
                    result['item'] = task.to_dict()
                else:
                    result['message'] = err or 'Task not found or you don\'t have permission.'

            elif action == 'delete_task':
                ok = task_service.delete(data.get('id'), user.id)
                result['success'] = ok
                result['message'] = '✅ Task deleted.' if ok else '❌ Could not delete task — not found or unauthorized.'

            elif action == 'create_plan':
                plan, err = plan_service.create(user.id, data)
                if plan:
                    result['success'] = True
                    result['message'] = f'✅ Plan "{plan.title}" added to your schedule!'
                    result['item'] = plan.to_dict()
                else:
                    result['message'] = err or 'Failed to create plan.'

            elif action == 'update_plan':
                plan, err = plan_service.update(data.get('id'), user.id, data)
                if plan:
                    result['success'] = True
                    result['message'] = f'✅ Plan "{plan.title}" updated!'
                    result['item'] = plan.to_dict()
                else:
                    result['message'] = err or 'Plan not found.'

            elif action == 'create_doc':
                if not user.can_create_doc():
                    result['message'] = '🔒 Document limit reached. Upgrade to Pro for unlimited documents.'
                    return result
                doc, err = doc_service.create(user.id, data)
                if doc:
                    result['success'] = True
                    result['message'] = f'✅ Document "{doc.title}" created and saved!'
                    result['item'] = doc.to_dict()
                else:
                    result['message'] = err or 'Failed to create document.'

            elif action == 'update_doc':
                doc, err = doc_service.update(data.get('id'), user.id, data)
                if doc:
                    result['success'] = True
                    result['message'] = f'✅ Document "{doc.title}" updated!'
                    result['item'] = doc.to_dict()
                else:
                    result['message'] = err or 'Document not found.'

        except Exception as e:
            result['message'] = f'Action error: {str(e)}'
            current_app.logger.error(f'AI action error: {e}')

        return result

    def chat(self, user, messages: list, context: dict = None, service: str = None, model_override: str = None) -> str:
        try:
            # Get model from admin config
            model = model_override or self._get_ai_config('ai_model', 'llama-3.1-8b-instant')
            max_tokens = int(self._get_ai_config('ai_max_tokens', '1500'))
            temperature = float(self._get_ai_config('ai_temperature', '0.7'))

            client = self._client()
            ctx    = context or self._build_context(user)
            system = self._system_prompt(user, ctx, service=service)

            all_messages = [{'role': 'system', 'content': system}] + messages

            response = client.chat.completions.create(
                model       = model,
                messages    = all_messages,
                max_tokens  = max_tokens,
                temperature = temperature,
            )
            return response.choices[0].message.content

        except Exception as e:
            root = e.__cause__ or e
            current_app.logger.error(f'Groq AI error: {e} | root: {type(root).__name__}: {root}')
            return (
                "⚠️ I'm having trouble connecting to the AI service right now. "
                "Please check your GROQ_API_KEY in .env or try again shortly."
            )

    def _client(self):
        return Groq(api_key=current_app.config['GROQ_API_KEY'])

    def summarize_tasks(self, user) -> str:
        tasks = Task.query.filter(
            Task.user_id == user.id,
            Task.status != 'done'
        ).limit(20).all()
        if not tasks:
            return "You have no active tasks — great time to plan something new! 🎉"
        task_list = '\n'.join(
            f'- [{t.id}] {t.title} [{t.priority} priority, {t.status}]'
            + (f' due {t.due_date}' if t.due_date else '')
            for t in tasks
        )
        msgs = [{'role': 'user', 'content':
            f'Summarize these active tasks. Identify top 3 priorities, flag overdue items, and give me an action plan:\n{task_list}'}]
        return self.chat(user, msgs)

    def suggest_plan(self, user, date_str: str) -> str:
        tasks = Task.query.filter(
            Task.user_id == user.id,
            Task.status.in_(['todo', 'in_progress']),
        ).order_by(Task.due_date, Task.priority.desc()).limit(10).all()
        task_list = 'No pending tasks.' if not tasks else '\n'.join(
            f'- [{t.id}] {t.title} (due: {t.due_date or "no date"}, {t.priority} priority)'
            for t in tasks
        )
        msgs = [{'role': 'user', 'content':
            f'Create a detailed daily plan for {date_str}. Assign time blocks (e.g. 09:00-10:30). Pending tasks:\n{task_list}'}]
        return self.chat(user, msgs)

    def generate_doc(self, user, doc_type: str, context: str) -> str:
        msgs = [{'role': 'user', 'content':
            f'Generate a professional {doc_type} document. Context:\n{context}\nFormat with clear sections and professional tone.'}]
        return self.chat(user, msgs)
