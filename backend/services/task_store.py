import asyncio
import uuid
from typing import Optional

from models.schemas import Task, TaskCreate, TaskStatus, SSEEvent, SSEEventType


class TaskStore:
    """In-memory task store. Good enough for hackathon demo."""

    def __init__(self):
        self.tasks: dict[str, Task] = {}
        self.event_queue: asyncio.Queue = asyncio.Queue()
        self._seed_demo_tasks()

    def _seed_demo_tasks(self):
        """Pre-load demo scenarios so dashboard has data on startup."""
        demo_tasks = [
            TaskCreate(
                company="Comcast",
                action="negotiate_rate",
                phone_number="+18005551234",
                service_type="internet",
                current_rate=85.0,
                target_rate=65.0,
                user_name="Neel",
                notes="Bill increased from $55 to $85. Negotiate back down.",
            ),
            TaskCreate(
                company="Planet Fitness",
                action="cancel_service",
                phone_number="+18005555678",
                service_type="gym",
                current_rate=25.0,
                user_name="Neel",
                notes="Cancel membership. Haven't been in 3 months.",
            ),
        ]
        for tc in demo_tasks:
            self.create_task(tc)

    def create_task(self, task_create: TaskCreate) -> Task:
        task_id = f"task_{uuid.uuid4().hex[:8]}"
        task = Task(id=task_id, **task_create.model_dump())
        self.tasks[task_id] = task
        return task

    def get_task(self, task_id: str) -> Optional[Task]:
        return self.tasks.get(task_id)

    def list_tasks(self) -> list[Task]:
        return list(self.tasks.values())

    def update_task(self, task_id: str, **kwargs) -> Optional[Task]:
        task = self.tasks.get(task_id)
        if not task:
            return None
        for key, value in kwargs.items():
            if hasattr(task, key):
                setattr(task, key, value)
        return task

    async def push_event(self, event: SSEEvent):
        """Push event to SSE queue for dashboard."""
        await self.event_queue.put(event)

    async def push_task_update(self, task: Task):
        """Convenience: push a task update event."""
        await self.push_event(SSEEvent(
            type=SSEEventType.TASK_UPDATED,
            data=task.model_dump(),
        ))


# Singleton
store = TaskStore()
