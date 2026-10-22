import os

class Jobs:
    def __init__(self, w):
        self.w = w

    def _run(self, env, params):
        return self.w.jobs.run_now(job_id=int(os.environ[env]), job_parameters=params).run_id

    def run_publish(self, fix_ids):
        """The T0 batch job: one run for every claimed fix id."""
        return self._run("PUBLISH_JOB_ID", {"fix_ids": ",".join(fix_ids)})

    def run_reset(self):
        return self._run("RESET_JOB_ID", {})

    def _run_state(self, run_id, env):
        """Life-cycle state of a run of the job in env, or None if the run is unknown or belongs to another job."""
        try:
            r = self.w.jobs.get_run(run_id)
        except Exception as e:  # unknown or inaccessible run id
            print(f"run state {run_id}: {type(e).__name__}: {e}")
            return None
        if r.job_id != int(os.environ[env]):
            return None
        st = r.state
        val = lambda x: getattr(x, "value", x) if x is not None else None
        return {"run_id": run_id, "life_cycle_state": val(st.life_cycle_state) if st else None,
                "result_state": val(st.result_state) if st else None}

    def reset_state(self, run_id):
        """Life-cycle state of a reset job run, or None if the run is not a reset run."""
        return self._run_state(run_id, "RESET_JOB_ID")

    def publish_state(self, run_id):
        """Life-cycle state of a publish job run (Approve all T0), or None if the run is not a publish run."""
        return self._run_state(run_id, "PUBLISH_JOB_ID")

    def run_inject(self, truth):
        return self._run("PRODUCE_JOB_ID", {"inject": truth, "minutes": "0"})
