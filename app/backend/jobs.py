import os

class Jobs:
    def __init__(self, w):
        self.w = w

    def _run(self, env, params):
        return self.w.jobs.run_now(job_id=int(os.environ[env]), job_parameters=params).run_id

    def run_publish(self, sid):
        return self._run("PUBLISH_JOB_ID", {"suggestion_id": sid})

    def run_reset(self):
        return self._run("RESET_JOB_ID", {})

    def run_inject(self, truth):
        return self._run("PRODUCE_JOB_ID", {"inject": truth, "minutes": "0"})
