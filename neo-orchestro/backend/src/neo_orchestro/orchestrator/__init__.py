"""Asynchronous orchestration: Celery app, dispatcher, scan runner (ADR 0007).

Nothing here is imported by the API except the dispatcher; the worker entry point is
``neo_orchestro.orchestrator.worker``.
"""
