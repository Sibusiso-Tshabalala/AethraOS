from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional


# =========================================================
# TASK STEP
# =========================================================

@dataclass
class TaskStep:
    """
    Represents one individual action inside a task.
    """

    description: str
    status: str = "pending"
    started_at: Optional[str] = None
    finished_at: Optional[str] = None
    error: Optional[str] = None

    def is_complete(self) -> bool:
        return self.status == "completed"

    def is_failed(self) -> bool:
        return self.status == "failed"

    def is_running(self) -> bool:
        return self.status == "in_progress"

    def is_waiting(self) -> bool:
        return self.status == "waiting_for_approval"


# =========================================================
# TASK
# =========================================================

@dataclass
class Task:
    """
    Represents an AethraOS task.

    A task can contain multiple individual TaskStep objects.
    """

    request: str

    steps: List[TaskStep] = field(
        default_factory=list
    )

    status: str = "pending"

    created_at: str = field(
        default_factory=lambda: datetime.now().isoformat(
            timespec="seconds"
        )
    )

    finished_at: Optional[str] = None

    error: Optional[str] = None

    # -----------------------------------------------------
    # STEP MANAGEMENT
    # -----------------------------------------------------

    def add_step(self, description: str) -> TaskStep:
        step = TaskStep(
            description=description
        )

        self.steps.append(step)

        return step

    # -----------------------------------------------------
    # TASK LIFECYCLE
    # -----------------------------------------------------

    def start(self):

        if self.status not in {
            "completed",
            "failed"
        }:

            self.status = "running"

            self.finished_at = None

            self.error = None

    def complete(self):

        self.status = "completed"

        self.finished_at = datetime.now().isoformat(
            timespec="seconds"
        )

        self.error = None

    def fail(
        self,
        error: Optional[str] = None
    ):

        self.status = "failed"

        self.finished_at = datetime.now().isoformat(
            timespec="seconds"
        )

        self.error = error

    def wait_for_approval(self):

        self.status = "waiting_for_approval"

        self.finished_at = None


# =========================================================
# TASK ENGINE
# =========================================================

class TaskEngine:
    """
    AethraOS task management engine.

    Responsibilities:

    - Create tasks
    - Track individual task steps
    - Track step execution state
    - Track task execution state
    - Track permissions
    - Track timestamps
    - Track failures
    - Provide task progress
    - Provide detailed task summaries
    - Support future task planning
    """

    def __init__(self):

        self.current_task: Optional[Task] = None

    # =====================================================
    # TASK CREATION
    # =====================================================

    def create_task(
        self,
        request: str
    ) -> Task:

        self.current_task = Task(
            request=request
        )

        return self.current_task

    # =====================================================
    # STEP CREATION
    # =====================================================

    def add_step(
        self,
        description: str
    ) -> Optional[TaskStep]:

        if not self.current_task:

            return None

        return self.current_task.add_step(
            description
        )

    def add_steps(
        self,
        descriptions: List[str]
    ) -> List[TaskStep]:

        """
        Add multiple planned steps at once.

        This is useful when the Brain eventually creates
        a complete task plan before execution.
        """

        created_steps = []

        if not self.current_task:

            return created_steps

        for description in descriptions:

            step = self.add_step(
                description
            )

            if step:

                created_steps.append(
                    step
                )

        return created_steps

    # =====================================================
    # TASK PLANNING
    # =====================================================

    def plan_steps(
        self,
        descriptions: List[str]
    ) -> List[TaskStep]:

        """
        Create a task plan without starting execution.

        Example:

            engine.plan_steps([
                "Open Visual Studio Code",
                "Create Python file",
                "Write Python code",
                "Save the file"
            ])

        The steps remain pending until the Brain starts them.
        """

        return self.add_steps(
            descriptions
        )

    # =====================================================
    # STEP TRACKING
    # =====================================================

    def start_step(
        self,
        step: Optional[TaskStep]
    ):

        if not step:

            return

        step.status = "in_progress"

        step.started_at = datetime.now().isoformat(
            timespec="seconds"
        )

        step.finished_at = None

        step.error = None

        # If the task was waiting for permission and
        # permission has now been granted, resume it.
        if self.current_task:

            if self.current_task.status == "waiting_for_approval":

                self.current_task.status = "running"

                self.current_task.finished_at = None

    def complete_step(
        self,
        step: Optional[TaskStep]
    ):

        if not step:

            return

        step.status = "completed"

        step.finished_at = datetime.now().isoformat(
            timespec="seconds"
        )

        step.error = None

    def fail_step(
        self,
        step: Optional[TaskStep],
        error: Optional[str] = None
    ):

        if not step:

            return

        step.status = "failed"

        step.finished_at = datetime.now().isoformat(
            timespec="seconds"
        )

        step.error = error

    def wait_for_approval(
        self,
        step: Optional[TaskStep] = None
    ):

        if not self.current_task:

            return

        if step:

            step.status = "waiting_for_approval"

        self.current_task.wait_for_approval()

    # =====================================================
    # CURRENT STEP
    # =====================================================

    def get_current_step(
        self
    ) -> Optional[TaskStep]:

        """
        Return the step currently being executed.
        """

        if not self.current_task:

            return None

        for step in self.current_task.steps:

            if step.status == "in_progress":

                return step

        return None

    def get_current_step_number(
        self
    ) -> Optional[int]:

        """
        Return the human-readable step number.

        Example:

            Step 2 of 5
        """

        if not self.current_task:

            return None

        for index, step in enumerate(
            self.current_task.steps,
            start=1
        ):

            if step.status == "in_progress":

                return index

        return None

    def get_current_step_description(
        self
    ) -> str:

        step = self.get_current_step()

        if not step:

            return ""

        return step.description

    # =====================================================
    # TASK STATUS
    # =====================================================

    def start_task(self):

        if self.current_task:

            self.current_task.start()

    def complete_task(self):

        if not self.current_task:

            return

        # Never complete a task while any step is still
        # pending, running, waiting for permission, or failed.
        unfinished_or_failed = any(

            step.status in {
                "failed",
                "waiting_for_approval",
                "in_progress",
                "pending",
            }

            for step in self.current_task.steps
        )

        if unfinished_or_failed:

            return

        self.current_task.complete()

    def fail_task(
        self,
        error: Optional[str] = None
    ):

        if self.current_task:

            self.current_task.fail(
                error
            )

    # =====================================================
    # TASK STATE HELPERS
    # =====================================================

    def has_active_task(self) -> bool:

        return self.current_task is not None

    def has_unfinished_steps(self) -> bool:

        if not self.current_task:

            return False

        return any(

            step.status in {
                "pending",
                "in_progress",
                "waiting_for_approval",
            }

            for step in self.current_task.steps
        )

    def has_failed_steps(self) -> bool:

        if not self.current_task:

            return False

        return any(

            step.status == "failed"

            for step in self.current_task.steps
        )

    # =====================================================
    # STATUS
    # =====================================================

    def get_status(
        self
    ) -> str:

        if not self.current_task:

            return "No active task."

        return self.current_task.status

    # =====================================================
    # PROGRESS
    # =====================================================

    def get_progress(
        self
    ) -> str:

        if not self.current_task:

            return "No active task."

        steps = self.current_task.steps

        total = len(steps)

        if total == 0:

            return (
                "No tool steps have been "
                "recorded yet."
            )

        completed = sum(

            step.status == "completed"

            for step in steps
        )

        failed = sum(

            step.status == "failed"

            for step in steps
        )

        waiting = sum(

            step.status == "waiting_for_approval"

            for step in steps
        )

        in_progress = sum(

            step.status == "in_progress"

            for step in steps
        )

        pending = sum(

            step.status == "pending"

            for step in steps
        )

        return (
            f"{completed}/{total} steps completed; "
            f"{in_progress} in progress; "
            f"{pending} pending; "
            f"{waiting} waiting for approval; "
            f"{failed} failed."
        )

    # =====================================================
    # DETAILED PROGRESS
    # =====================================================

    def get_progress_details(
        self
    ) -> dict:

        """
        Structured progress information for the UI.

        This allows window.py to display information such as:

            Step 2 of 5
            Creating Python file
            1 completed
            1 in progress
            3 pending
        """

        if not self.current_task:

            return {
                "active": False,
                "status": "none",
                "current_step": None,
                "current_step_number": None,
                "total_steps": 0,
                "completed": 0,
                "in_progress": 0,
                "pending": 0,
                "waiting_for_approval": 0,
                "failed": 0,
                "description": "",
            }

        steps = self.current_task.steps

        total = len(steps)

        completed = 0
        in_progress = 0
        pending = 0
        waiting = 0
        failed = 0

        current_step = None
        current_step_number = None

        for index, step in enumerate(
            steps,
            start=1
        ):

            if step.status == "completed":

                completed += 1

            elif step.status == "in_progress":

                in_progress += 1

                current_step = step
                current_step_number = index

            elif step.status == "pending":

                pending += 1

            elif step.status == "waiting_for_approval":

                waiting += 1

                if current_step is None:

                    current_step = step
                    current_step_number = index

            elif step.status == "failed":

                failed += 1

        description = ""

        if current_step:

            description = current_step.description

        return {
            "active": True,
            "status": self.current_task.status,
            "current_step": current_step,
            "current_step_number": current_step_number,
            "total_steps": total,
            "completed": completed,
            "in_progress": in_progress,
            "pending": pending,
            "waiting_for_approval": waiting,
            "failed": failed,
            "description": description,
        }

    # =====================================================
    # TASK SUMMARY
    # =====================================================

    def get_task_summary(
        self
    ):

        if not self.current_task:

            return {
                "status": "none",
                "request": None,
                "progress": "No active task.",
                "current_step": None,
                "steps": [],
            }

        current_step = self.get_current_step()

        current_step_number = (
            self.get_current_step_number()
        )

        return {
            "status": self.current_task.status,

            "request": self.current_task.request,

            "created_at": self.current_task.created_at,

            "finished_at": self.current_task.finished_at,

            "error": self.current_task.error,

            "progress": self.get_progress(),

            "current_step": (
                current_step.description
                if current_step
                else None
            ),

            "current_step_number": (
                current_step_number
            ),

            "total_steps": len(
                self.current_task.steps
            ),

            "steps": [

                {
                    "description": step.description,

                    "status": step.status,

                    "started_at": step.started_at,

                    "finished_at": step.finished_at,

                    "error": step.error,

                }

                for step in self.current_task.steps
            ],
        }

    # =====================================================
    # RESET
    # =====================================================

    def clear(self):

        self.current_task = None