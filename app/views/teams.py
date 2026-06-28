"""
Team views — create, join, manage teams and leaderboards.
"""
from flask import (Blueprint, render_template, request, jsonify,
                   flash, redirect, url_for, abort)
from flask_login import login_required, current_user
from app.services.team_service import team_service
from app.models.team import Team, TeamMember
from app.utils.decorators import get_visible_menus

team_bp = Blueprint('teams', __name__)


# ── List / create ──────────────────────────────────────────────────────────────

@team_bp.route('/')
@login_required
def index():
    teams = team_service.get_user_teams(current_user.id)
    return render_template('teams/index.html',
                           teams=teams,
                           menus=get_visible_menus(current_user))


@team_bp.route('/create', methods=['POST'])
@login_required
def create():
    name = request.form.get('name', '').strip()
    description = request.form.get('description', '').strip()
    team, err = team_service.create_team(current_user.id, name, description)
    if err:
        flash(err, 'danger')
        return redirect(url_for('teams.index'))
    flash(f'Team "{team.name}" created!', 'success')
    return redirect(url_for('teams.detail', team_id=team.id))


# ── Join via invite ────────────────────────────────────────────────────────────

@team_bp.route('/join', methods=['POST'])
@login_required
def join():
    code = request.form.get('invite_code', '').strip()
    team, err = team_service.join_team(current_user.id, code)
    if err:
        flash(err, 'danger')
        return redirect(url_for('teams.index'))
    flash(f'Welcome to "{team.name}"!', 'success')
    return redirect(url_for('teams.detail', team_id=team.id))


# ── Team detail / leaderboard ──────────────────────────────────────────────────

@team_bp.route('/<int:team_id>')
@login_required
def detail(team_id):
    data, err = team_service.get_leaderboard(team_id, current_user.id)
    if err:
        flash(err, 'danger')
        return redirect(url_for('teams.index'))
    team = Team.query.get_or_404(team_id)
    my_role = 'visitor'
    m = team.get_member(current_user.id)
    if m:
        my_role = m.role
    return render_template('teams/detail.html',
                           team=team,
                           data=data,
                           my_role=my_role,
                           is_owner=team.is_owner(current_user.id),
                           menus=get_visible_menus(current_user))


# ── Settings ───────────────────────────────────────────────────────────────────

@team_bp.route('/<int:team_id>/settings', methods=['GET', 'POST'])
@login_required
def settings(team_id):
    team = Team.query.get_or_404(team_id)
    if not team.is_admin_or_owner(current_user.id):
        abort(403)

    if request.method == 'POST':
        action = request.form.get('action')

        if action == 'update':
            _, err = team_service.update_team(
                current_user.id, team_id,
                name=request.form.get('name'),
                description=request.form.get('description'),
            )
            flash(err or 'Team updated.', 'danger' if err else 'success')

        elif action == 'regenerate_invite':
            _, err = team_service.regenerate_invite(current_user.id, team_id)
            flash(err or 'New invite code generated.', 'danger' if err else 'success')

        elif action == 'remove_member':
            uid = request.form.get('user_id', type=int)
            _, err = team_service.remove_member(current_user.id, team_id, uid)
            flash(err or 'Member removed.', 'danger' if err else 'success')

        elif action == 'change_role':
            uid = request.form.get('user_id', type=int)
            role = request.form.get('role')
            _, err = team_service.update_member_role(current_user.id, team_id, uid, role)
            flash(err or 'Role updated.', 'danger' if err else 'success')

        elif action == 'delete':
            ok, err = team_service.delete_team(current_user.id, team_id)
            if ok:
                flash('Team deleted.', 'success')
                return redirect(url_for('teams.index'))
            flash(err, 'danger')

        return redirect(url_for('teams.settings', team_id=team_id))

    return render_template('teams/settings.html',
                           team=team,
                           menus=get_visible_menus(current_user))


# ── Leave ──────────────────────────────────────────────────────────────────────

@team_bp.route('/<int:team_id>/leave', methods=['POST'])
@login_required
def leave(team_id):
    ok, msg = team_service.leave_team(current_user.id, team_id)
    flash(msg, 'success' if ok else 'danger')
    return redirect(url_for('teams.index'))


# ── API ────────────────────────────────────────────────────────────────────────

@team_bp.route('/api/leaderboard/<int:team_id>')
@login_required
def api_leaderboard(team_id):
    data, err = team_service.get_leaderboard(team_id, current_user.id)
    if err:
        return jsonify({'error': err}), 403
    return jsonify(data)
