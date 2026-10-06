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

    def reset_state(self, run_id):
        """Life-cycle state of a reset job run, or None if the run is not a reset run."""
        r = self.w.jobs.get_run(run_id)
        if r.job_id != int(os.environ["RESET_JOB_ID"]):
            return None
        st = r.state
        val = lambda x: getattr(x, "value", x) if x is not None else None
        return {"run_id": run_id, "life_cycle_state": val(st.life_cycle_state) if st else None,
                "result_state": val(st.result_state) if st else None}

    def run_inject(self, truth):
        return self._run("PRODUCE_JOB_ID", {"inject": truth, "minutes": "0"})
