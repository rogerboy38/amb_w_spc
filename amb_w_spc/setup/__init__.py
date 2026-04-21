# Setup package for amb_w_spc.
# after_install was consolidated here from the shadowed amb_w_spc/setup.py
# because Python package resolution prefers this directory over the .py file,
# causing hooks.py reference `amb_w_spc.setup.after_install` to raise
# AttributeError on fresh install.
import frappe


def after_install():
    """Runs after amb_w_spc is installed on a site."""
    print("AMB W SPC App installed successfully!")
