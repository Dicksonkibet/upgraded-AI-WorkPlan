# WorkPro — Go-To-Market & User Acquisition Strategy

## Executive Summary

WorkPro is a campus productivity platform with a powerful but hidden AI core. The product is well-built — the gap is **awareness and activation**, not product quality. This strategy focuses on a zero-cost campus launch, viral loops through collaboration, and a conversion funnel designed to turn free users into paid subscribers.

---

## Target Audience

### Primary: University & College Students (Kenya & East Africa)
- Managing group projects, assignments, and personal goals
- Heavy mobile users, WhatsApp-first communication
- Price-sensitive — must see value clearly before paying
- Heavily influenced by peers ("if my classmate uses it, I should too")

### Secondary: Small Team Leads & Freelancers
- 2–8 person teams who outgrow WhatsApp group chats for task management
- Can afford KES 999/month if it genuinely saves time
- Likely to expense it or split the cost across a team

---

## The Core Viral Loop

The single biggest growth lever is **collaborative workspaces**.

> One person sets up WorkPro → invites teammates for a group project → teammates see the value → each creates their own account → some invite *their* groups.

Every feature you build should ask: **"Does this make someone want to share WorkPro with a friend?"**

---

## Phase 1 — Campus Seeding (Month 1–2)

### 1. Brand Ambassadors (Campus Reps)
Recruit 1–2 students per university, give them:
- A free Pro subscription
- A unique referral link (tracked in the system)
- A small incentive for every 10 signups from their link (e.g. extended Pro, airtime)

**Script for ambassadors:**
> "I use this AI productivity app for my assignments. It literally creates tasks for me just by describing what I need to do. Here's a link — it's free to start."

Target: Top 5 universities in Nairobi first (UoN, KU, Strathmore, USIU, JKUAT), then expand.

### 2. WhatsApp Group Drops
Create a short 60-second phone screen recording showing:
1. User types "Create task: submit CAT 2 by Friday, high priority" into the AI bar
2. Task appears instantly in the dashboard
3. Daily digest email arrives in the morning with their plan

Drop this clip into course WhatsApp groups. The AI moment is the hook — it's genuinely surprising.

### 3. Student Council & Class Rep Partnerships
Pitch to class reps: "Give your classmates a free tool to manage group CAT prep." Offer a shared workspace for their class group — everyone joins under one rep's invite.

---

## Phase 2 — Content & SEO (Month 2–4)

### Blog & Social Content (Low Cost)
Publish weekly on a simple blog (can be a shared WorkPro document published publicly):

- "How I stopped missing deadlines using an AI task manager"
- "5 things Kenyan students waste time on (and how to fix them)"
- "Group project chaos? Here's how we organised our final year project"
- "WorkPro vs Todoist vs Notion — what actually works for campus"

These rank on Google for "productivity app for students Kenya" and "task manager for students."

### Short-Form Video (TikTok / Instagram Reels)
15–30 second demos:
- Type a vague goal → AI breaks it into tasks instantly
- Show the streak counter hitting 10 days
- Before/after: WhatsApp chaos vs WorkPro board

No production budget needed — phone + screen record is authentic and performs well.

---

## Phase 3 — Activation Funnel (Ongoing)

The existing report identified that users "fall off a cliff" after registration. The onboarding checklist added in this improvement sprint directly addresses this, but here is the full funnel:

### Signup → First Value (Goal: < 5 minutes)
1. User registers → lands on dashboard with **onboarding checklist** visible
2. Step 1 prompt: "Create your first task" → one click opens modal
3. Step 2 prompt: "Plan your day" → AI bar is right there at the top
4. Step 3 prompt: "Try the AI" → pre-filled suggestion "Try typing: create task for me"
5. Checklist completes → green tick → "You're set! Here's what WorkPro can do for you."

### Day 2–7 Retention
- **Day 2 morning**: digest email arrives with their tasks ("Here's your plan for today, [Name]")
- **Day 3**: if they completed a task, streak badge appears on dashboard (🔥 2-day streak)
- **Day 5**: if no activity, send a re-engagement email: "Your tasks are waiting — you have 3 overdue"
- **Day 7**: prompt to invite a teammate or try the AI chat for a full project plan

### Free → Pro Conversion
The upgrade moment should feel **earned, not forced**. Three natural triggers:

1. **Task limit hit**: Banner appears — "You've used all 10 free tasks. Upgrade to continue. KES 999/month."
2. **AI limit hit**: Mid-conversation — "You've used your 5 free AI messages today. Pro users get unlimited. Upgrade?"
3. **Streak milestone**: At 7 days — "You're on a 7-day streak! Pro users see a full productivity report. Want to unlock it?"

---

## Pricing & Positioning

### Current: Free vs Pro (KES 999/month)
This works. The key is making the **free plan feel generous but limited at the right moments**.

Recommended free limits (if not already set):
- 10 tasks max
- 3 documents max
- 5 AI messages per day
- No recurring tasks, no digest email

### Potential Add: Team Plan (KES 2,500/month for up to 5 users)
Once shared workspaces are built, a team plan unlocks:
- Shared task board
- Team-wide AI that any member can query
- Admin dashboard for the team lead
- Shared documents with view/edit permissions

This is the campus group project plan — sell it to class reps and student organisations.

---

## Referral Programme

Build a referral system directly into the app:

- Every user gets a unique referral link at `/ref/[username]`
- Referred user gets 7 days of Pro free on signup
- Referrer gets 7 days of Pro credit per successful referral
- After 3 referrals: 1 free month of Pro

**Where to show referral links:**
- Dashboard sidebar ("Invite a friend — get Pro free")
- After first task created ("Nice! Know someone who'd love this? Share WorkPro")
- Streak badge area ("Share your streak with a friend")

---

## Metrics to Track (North Star)

| Metric | Target (Month 3) | Target (Month 6) |
|--------|-----------------|-----------------|
| Registered users | 500 | 2,000 |
| Day-7 retention | 30% | 40% |
| Free → Pro conversion | 5% | 8% |
| Referral rate (users who invite ≥1 person) | 15% | 25% |
| Daily active users | 100 | 600 |

---

## Quick Wins Checklist

These cost almost nothing and can be done this week:

- [ ] Add referral link to every user's profile page
- [ ] Set up WhatsApp Business number for support ("Text us if anything breaks")
- [ ] Create 3 task templates accessible from the tasks page: "Exam prep", "Group project", "Weekly review"
- [ ] Post the 60-second AI demo to your personal social channels and 3 campus WhatsApp groups
- [ ] Set up Google Analytics (or Plausible for privacy-friendly) to see where users drop off
- [ ] Write 1 blog post targeting "productivity app for students Kenya" — even 400 words helps

---

## Summary Priority Order

1. **Notifications** (digest + reminders) — biggest retention lever, now implemented ✓
2. **Onboarding checklist** — reduces day-1 dropoff, now implemented ✓
3. **Campus ambassador programme** — cheapest user acquisition channel
4. **Referral system** — compounds every other channel
5. **Team/shared workspaces** — unlocks viral loop and team plan revenue
6. **Content & SEO** — slow burn but compounds over time
