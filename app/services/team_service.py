"""
Team service — create, join, manage teams and compute leaderboards.
"""
from datetime import datetime
from flask import current_app
from app import db
from app.models.team import Team, TeamMember
from app.models.user import User
from app.models.task import Task


class TeamService:

    # ── Create / manage ────────────────────────────────────────────

    def create_team(self, owner_id: int, name: str, description: str = '') -> tuple:
        """Create a new team. Returns (team, error)."""
        name = name.strip()
        if not name or len(name) < 2:
            return None, 'Team name must be at least 2 characters.'
        if len(name) > 120:
            return None, 'Team name is too long (max 120 chars).'

        slug = Team.slugify(name)
        invite = Team.generate_invite_code()

        team = Team(
            name=name,
            slug=slug,
            description=(description or '').strip()[:500],
            owner_id=owner_id,
            invite_code=invite,
        )
        db.session.add(team)
        db.session.flush()   # get team.id before adding member

        # owner is always a member with role 'owner'
        member = TeamMember(team_id=team.id, user_id=owner_id, role='owner')
        db.session.add(member)
        db.session.commit()
        return team, None

    def join_team(self, user_id: int, invite_code: str) -> tuple:
        """Join a team via invite code. Returns (team, error)."""
        team = Team.query.filter_by(invite_code=invite_code.upper().strip()).first()
        if not team:
            return None, 'Invalid invite code. Please check and try again.'

        existing = TeamMember.query.filter_by(
            team_id=team.id, user_id=user_id
        ).first()
        if existing:
            if existing.is_active:
                return None, 'You are already a member of this team.'
            # Re-activate if previously left
            existing.is_active = True
            existing.joined_at = datetime.utcnow()
            db.session.commit()
            return team, None

        member = TeamMember(team_id=team.id, user_id=user_id, role='member')
        db.session.add(member)
        db.session.commit()
        return team, None

    def leave_team(self, user_id: int, team_id: int) -> tuple:
        """Leave a team. Owners must transfer ownership first."""
        team = Team.query.get(team_id)
        if not team:
            return False, 'Team not found.'
        if team.owner_id == user_id:
            return False, 'You are the team owner. Transfer ownership before leaving.'
        member = TeamMember.query.filter_by(
            team_id=team_id, user_id=user_id, is_active=True
        ).first()
        if not member:
            return False, 'You are not a member of this team.'
        member.is_active = False
        db.session.commit()
        return True, 'You have left the team.'

    def remove_member(self, requester_id: int, team_id: int, member_user_id: int) -> tuple:
        team = Team.query.get(team_id)
        if not team:
            return False, 'Team not found.'
        if not team.is_admin_or_owner(requester_id):
            return False, 'Permission denied.'
        if member_user_id == team.owner_id:
            return False, 'Cannot remove the team owner.'
        member = TeamMember.query.filter_by(
            team_id=team_id, user_id=member_user_id, is_active=True
        ).first()
        if not member:
            return False, 'Member not found.'
        member.is_active = False
        db.session.commit()
        return True, 'Member removed.'

    def update_member_role(self, requester_id: int, team_id: int,
                           member_user_id: int, new_role: str) -> tuple:
        if new_role not in ('admin', 'member'):
            return False, 'Invalid role.'
        team = Team.query.get(team_id)
        if not team:
            return False, 'Team not found.'
        if not team.is_owner(requester_id):
            return False, 'Only the owner can change roles.'
        member = TeamMember.query.filter_by(
            team_id=team_id, user_id=member_user_id, is_active=True
        ).first()
        if not member:
            return False, 'Member not found.'
        member.role = new_role
        db.session.commit()
        return True, f'Role updated to {new_role}.'

    def update_team(self, requester_id: int, team_id: int,
                    name: str = None, description: str = None) -> tuple:
        team = Team.query.get(team_id)
        if not team:
            return None, 'Team not found.'
        if not team.is_admin_or_owner(requester_id):
            return None, 'Permission denied.'
        if name:
            name = name.strip()
            if len(name) < 2:
                return None, 'Name too short.'
            team.name = name[:120]
        if description is not None:
            team.description = description.strip()[:500]
        team.updated_at = datetime.utcnow()
        db.session.commit()
        return team, None

    def regenerate_invite(self, requester_id: int, team_id: int) -> tuple:
        """Generate a new invite code (invalidates the old one)."""
        team = Team.query.get(team_id)
        if not team:
            return None, 'Team not found.'
        if not team.is_admin_or_owner(requester_id):
            return None, 'Permission denied.'
        team.invite_code = Team.generate_invite_code()
        db.session.commit()
        return team.invite_code, None

    def delete_team(self, requester_id: int, team_id: int) -> tuple:
        team = Team.query.get(team_id)
        if not team:
            return False, 'Team not found.'
        if not team.is_owner(requester_id):
            return False, 'Only the team owner can delete the team.'
        db.session.delete(team)
        db.session.commit()
        return True, 'Team deleted.'

    # ── Queries ────────────────────────────────────────────────────

    def get_user_teams(self, user_id: int):
        """All teams the user belongs to (active memberships)."""
        memberships = TeamMember.query.filter_by(
            user_id=user_id, is_active=True
        ).all()
        return [m.team for m in memberships if m.team]

    def get_team_by_id(self, team_id: int, user_id: int):
        """Get team if user is a member."""
        team = Team.query.get(team_id)
        if not team:
            return None
        if not team.get_member(user_id) and team.owner_id != user_id:
            return None
        return team

    # ── Leaderboard ────────────────────────────────────────────────

    def get_leaderboard(self, team_id: int, user_id: int) -> tuple:
        """
        Returns leaderboard data for the team.
        Only members can view.
        Scores = tasks completed (status='done').
        """
        team = Team.query.get(team_id)
        if not team:
            return None, 'Team not found.'
        if not team.get_member(user_id) and team.owner_id != user_id:
            return None, 'Access denied.'

        members = team.members.filter_by(is_active=True).all()
        rows = []
        for m in members:
            user = m.user
            if not user:
                continue
            done = Task.query.filter_by(user_id=user.id, status='done').count()
            total = Task.query.filter_by(user_id=user.id).count()
            rows.append({
                'user_id':    user.id,
                'name':       user.full_name,
                'initials':   user.initials,
                'color':      user.avatar_color,
                'role':       m.role,
                'tasks_done': done,
                'tasks_total': total,
                'is_pro':     user.is_pro,
                'streak':     user.streak_days or 0,
            })

        rows.sort(key=lambda r: (-r['tasks_done'], -r['streak']))
        for i, r in enumerate(rows):
            r['rank'] = i + 1

        return {'team': team.to_dict(), 'members': rows}, None

    # ── Stats for current user ─────────────────────────────────────

    def get_user_team_summary(self, user_id: int) -> dict:
        teams = self.get_user_teams(user_id)
        return {
            'count': len(teams),
            'teams': [t.to_dict() for t in teams],
        }


team_service = TeamService()
