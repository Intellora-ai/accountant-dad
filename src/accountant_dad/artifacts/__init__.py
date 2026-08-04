"""The six canonical artifacts. One module each, one owning engine each.

`DATA_FLOW.md` §2: every arrow between engines carries exactly one named
artifact, and no engine may consume the internals of the engine that produced
it. Each module here is one of those six names and nothing else.

Nothing is re-exported. A caller imports the artifact it actually needs, so
the import graph shows which engine depends on which contract.
"""
