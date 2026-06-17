"""Compatibility package for older Render start commands.

The rebuilt app lives in `api.main`. Some Render services may still start
`uvicorn backend.main:app`; this package keeps that command working.
"""
