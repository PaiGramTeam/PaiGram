from telegram.ext import CallbackContext


class BaseJob:

    @staticmethod
    def remove_job_if_exists(name: str, context: CallbackContext) -> bool:
        current_jobs = context.job_queue.get_jobs_by_name(name)
        if not current_jobs:
            return False
        for job in current_jobs:
            job.schedule_removal()
        return True
