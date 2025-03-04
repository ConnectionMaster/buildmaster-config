import re
from buildbot.schedulers.basic import AnyBranchScheduler
from twisted.internet import defer
from twisted.python import log


class GitHubPrScheduler(AnyBranchScheduler):
    def __init__(self, *args, stable_builder_names, **kwargs):
        super().__init__(*args, **kwargs)
        self.stable_builder_names = stable_builder_names

    @defer.inlineCallbacks
    def addBuildsetForChanges(self, **kwargs):
        log.msg("Preparing buildset for PR changes")
        changeids = kwargs.get("changeids")
        if changeids is None or len(changeids) == 0:
            log.msg("No changeids found")
            yield super().addBuildsetForChanges(**kwargs)
            return

        # It is possible that we get multiple changeids if there are multiple
        # requests being made in quick succession. All these changeids will
        # have the same properties, so we can just pick the first one.
        changeid = changeids[0]
        change = yield self.master.db.changes.getChange(changeid)

        builder_filter = change.properties.get("builderfilter", None)
        event = change.properties.get("event", None)
        if event:
            # looks like `("issue_comment", "Change")` for a comment
            event, _ = event
        builder_names = kwargs.get("builderNames", self.builderNames)
        if builder_filter and builder_names:
            # allow unstable builders only for comment-based trigger
            if event != "issue_comment":
                builder_names = [
                    builder_name
                    for builder_name in builder_names
                    if builder_name in self.stable_builder_names
                ]
                log.msg(f"Considering only stable builders: {builder_names}")
            # looks like `("<filter regex from comment>", "Change")`
            builder_filter, _ = builder_filter
            log.msg(f"Found builder filter: {builder_filter}")
            matcher = re.compile(builder_filter, re.IGNORECASE)
            builder_names = [
                builder_name
                for builder_name in builder_names
                if matcher.search(builder_name)
            ]
            if builder_names:
                log.msg(f"Builder names filtered: {builder_names}")
                kwargs.update(builderNames=builder_names)
                yield super().addBuildsetForChanges(**kwargs)
            else:
                log.msg("No matching builders after filtering - breaking out")
            return

        log.msg("Scheduling regular non-filtered buildset")
        yield super().addBuildsetForChanges(**kwargs)
        return
