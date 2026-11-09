"""Job data directories for tests that build a ``TrainingJob`` without a job loop."""

from __future__ import annotations

from aster.core.job_data import JobData
from aster.storage.data import MemoryDataStore
from aster.storage.job_data import JobDataRef
from aster.storage.tasks import LocalTaskFileStore


def job_data_ref(data: JobData) -> JobDataRef:
    """``data`` written as a job data directory by a new in-memory data store."""
    return MemoryDataStore(LocalTaskFileStore()).write_job_directory(data)
