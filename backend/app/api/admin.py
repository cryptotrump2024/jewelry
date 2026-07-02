"""Admin API (Phase 5 backend) — CRUD for templates/option groups/rules with

rule preview + simulator-gated publish (docs/spec/03 FRD admin module).
Everything is tenant-scoped through the repository layer. Staff
authentication/roles arrive with the admin UI; endpoints are engine-internal
until then.
"""

import uuid
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.api.routes import DbSession
from app.models import (
    Option,
    OptionGroup,
    ProductTemplate,
    Rule,
    RuleSet,
    TemplateOptionGroup,
)
from app.rules.engine import RuleData
from app.rules.simulator import simulate_rule_set
from app.tenancy.repository import TenantScopedRepository

router = APIRouter(prefix="/admin", tags=["admin"])


class TemplateRepo(TenantScopedRepository[ProductTemplate]):
    model = ProductTemplate


class OptionGroupRepo(TenantScopedRepository[OptionGroup]):
    model = OptionGroup


class RuleSetRepo(TenantScopedRepository[RuleSet]):
    model = RuleSet


# --- Schemas ---


class TemplateCreate(BaseModel):
    category_id: uuid.UUID
    code: str = Field(min_length=1, max_length=100)
    name: str
    style: str | None = None
    status: str = "draft"
    is_bespoke_base: bool = False


class TemplateUpdate(BaseModel):
    name: str | None = None
    style: str | None = None
    status: str | None = None


class OptionGroupCreate(BaseModel):
    key: str
    name: str
    ui_type: str = "select"
    sort: int = 0


class OptionCreate(BaseModel):
    code: str
    label: str
    value: dict[str, Any] | None = None
    sort: int = 0
    is_active: bool = True


class AttachGroup(BaseModel):
    option_group_id: uuid.UUID
    step_order: int = 0
    is_required: bool = True
    default_option_id: uuid.UUID | None = None


class RuleCreate(BaseModel):
    type: str
    condition: dict[str, Any]
    effect: dict[str, Any]
    message: str | None = None
    scope: dict[str, Any] | None = None
    sort: int = 0


# --- Templates ---


@router.get("/templates")
async def list_templates(session: DbSession) -> list[dict]:
    templates = await TemplateRepo(session).list()
    return [
        {"id": str(t.id), "code": t.code, "name": t.name, "status": t.status}
        for t in templates
    ]


@router.post("/templates", status_code=201)
async def create_template(payload: TemplateCreate, session: DbSession) -> dict:
    template = TemplateRepo(session).create(**payload.model_dump())
    await session.commit()
    return {"id": str(template.id), "code": template.code}


@router.patch("/templates/{template_id}")
async def update_template(template_id: uuid.UUID, payload: TemplateUpdate, session: DbSession):
    template = await TemplateRepo(session).get(template_id)
    if template is None:
        raise HTTPException(404, "template not found")
    for key, value in payload.model_dump(exclude_none=True).items():
        setattr(template, key, value)
    await session.commit()
    return {"id": str(template.id), "status": template.status}


@router.post("/templates/{template_id}/option-groups", status_code=201)
async def attach_option_group(template_id: uuid.UUID, payload: AttachGroup, session: DbSession):
    template = await TemplateRepo(session).get(template_id)
    if template is None:
        raise HTTPException(404, "template not found")
    group = await OptionGroupRepo(session).get(payload.option_group_id)
    if group is None:
        raise HTTPException(404, "option group not found")
    session.add(TemplateOptionGroup(template_id=template.id, **payload.model_dump()))
    await session.commit()
    return {"ok": True}


# --- Option groups & options ---


@router.post("/option-groups", status_code=201)
async def create_option_group(payload: OptionGroupCreate, session: DbSession) -> dict:
    group = OptionGroupRepo(session).create(**payload.model_dump())
    await session.commit()
    return {"id": str(group.id), "key": group.key}


@router.post("/option-groups/{group_id}/options", status_code=201)
async def create_option(group_id: uuid.UUID, payload: OptionCreate, session: DbSession) -> dict:
    group = await OptionGroupRepo(session).get(group_id)
    if group is None:
        raise HTTPException(404, "option group not found")
    option = Option(option_group_id=group.id, **payload.model_dump())
    session.add(option)
    await session.commit()
    return {"id": str(option.id), "code": option.code}


# --- Rule sets: draft → simulate → publish ---


@router.post("/templates/{template_id}/rule-sets", status_code=201)
async def create_rule_set(template_id: uuid.UUID, session: DbSession) -> dict:
    """Create the next draft version for a template."""
    repo = RuleSetRepo(session)
    template = await TemplateRepo(session).get(template_id)
    if template is None:
        raise HTTPException(404, "template not found")
    existing = (
        await session.execute(
            select(RuleSet.version)
            .where(RuleSet.tenant_id == repo.tenant_id, RuleSet.template_id == template.id)
            .order_by(RuleSet.version.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    rule_set = repo.create(template_id=template.id, version=(existing or 0) + 1, status="draft")
    await session.commit()
    return {"id": str(rule_set.id), "version": rule_set.version, "status": rule_set.status}


@router.post("/rule-sets/{rule_set_id}/rules", status_code=201)
async def add_rule(rule_set_id: uuid.UUID, payload: RuleCreate, session: DbSession) -> dict:
    rule_set = await RuleSetRepo(session).get(rule_set_id)
    if rule_set is None:
        raise HTTPException(404, "rule set not found")
    if rule_set.status != "draft":
        raise HTTPException(409, "only draft rule sets can be edited")
    rule = Rule(rule_set_id=rule_set.id, **payload.model_dump())
    session.add(rule)
    await session.commit()
    return {"id": str(rule.id)}


async def _group_options_for_template(session, template_id: uuid.UUID) -> dict[str, list[str]]:
    links = (
        (
            await session.execute(
                select(TemplateOptionGroup, OptionGroup)
                .join(OptionGroup, OptionGroup.id == TemplateOptionGroup.option_group_id)
                .where(TemplateOptionGroup.template_id == template_id)
                .order_by(TemplateOptionGroup.step_order)
            )
        )
        .all()
    )
    result: dict[str, list[str]] = {}
    for _link, group in links:
        options = (
            (
                await session.execute(
                    select(Option.code).where(
                        Option.option_group_id == group.id, Option.is_active.is_(True)
                    )
                )
            )
            .scalars()
            .all()
        )
        result[group.key] = list(options)
    return result


async def _simulate(session, rule_set: RuleSet) -> dict:
    await session.refresh(rule_set, ["rules"])
    rules = [
        RuleData(
            type=r.type,
            condition=r.condition,
            effect=r.effect,
            message=r.message,
            scope=r.scope,
            sort=r.sort,
        )
        for r in rule_set.rules
    ]
    group_options = await _group_options_for_template(session, rule_set.template_id)
    if not group_options:
        raise HTTPException(409, "template has no option groups attached — nothing to simulate")
    report = simulate_rule_set(rules, group_options)
    return {
        "ok": report.ok,
        "total_combinations": report.total_combinations,
        "valid": report.valid_count,
        "invalid": report.invalid_count,
        "quote_only": report.quote_only_count,
        "always_blocked": report.always_blocked,
        "dead_options": report.dead_options,
        "contradictions": report.contradictions,
        "sampled": report.sampled,
    }


@router.get("/rule-sets/{rule_set_id}/simulate")
async def simulate_rules(rule_set_id: uuid.UUID, session: DbSession) -> dict:
    """Preview: what would this rule set do across all combinations?"""
    rule_set = await RuleSetRepo(session).get(rule_set_id)
    if rule_set is None:
        raise HTTPException(404, "rule set not found")
    return await _simulate(session, rule_set)


@router.post("/rule-sets/{rule_set_id}/publish")
async def publish_rule_set(rule_set_id: uuid.UUID, session: DbSession) -> dict:
    """Publish is refused when the simulator finds contradictions

    (docs/spec/07 §9 case 8) — bad rule sets never reach a customer.
    """
    from datetime import UTC, datetime

    rule_set = await RuleSetRepo(session).get(rule_set_id)
    if rule_set is None:
        raise HTTPException(404, "rule set not found")
    if rule_set.status == "published":
        raise HTTPException(409, "rule set already published")

    report = await _simulate(session, rule_set)
    if not report["ok"]:
        raise HTTPException(
            status_code=422,
            detail={"message": "rule set failed simulation", "report": report},
        )

    rule_set.status = "published"
    rule_set.published_at = datetime.now(UTC)
    await session.commit()
    return {
        "id": str(rule_set.id),
        "version": rule_set.version,
        "status": rule_set.status,
        "report": report,
    }
