"""Smoke tests that actually execute the dashboard script.

The unit tests cover the physics and the model, but they cannot catch a
dashboard that raises on load -- a broken rendering call, a missing optional
dependency, or an unguarded reference when no site is viable. Streamlit's
``AppTest`` runs ``app.py`` in-process and surfaces any exception the script
would have shown the user, so these tests fail the same way the demo would.
"""

from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("streamlit")

from streamlit.testing.v1 import AppTest  # noqa: E402

APP = str(Path(__file__).resolve().parent.parent / "app.py")
TIMEOUT_S = 300  # the first run trains the model


def widget_by_label(elements, label: str):
    """Find a widget by its label.

    Positional lookup is brittle: AppTest orders widgets by their position in
    the element tree, not by the order they appear in the source, so adding a
    control to the main body silently renumbers the sidebar.
    """
    for element in elements:
        if label in element.label:
            return element
    raise AssertionError(
        f"no widget labelled {label!r}; found {[e.label for e in elements]}"
    )


def run_app(population: int | None = None, propellant: bool | None = None) -> AppTest:
    app = AppTest.from_file(APP, default_timeout=TIMEOUT_S)
    app.run()
    changed = False
    if population is not None:
        widget_by_label(app.slider, "Settlement population").set_value(population)
        changed = True
    if propellant is not None:
        widget_by_label(app.checkbox, "return propellant").set_value(propellant)
        changed = True
    if changed:
        app.run()
    return app


def assert_clean(app: AppTest) -> None:
    assert not app.exception, [str(e.value) for e in app.exception]


@pytest.fixture(scope="module")
def default_app():
    return run_app()


class TestDashboardLoads:
    def test_script_runs_without_raising(self, default_app):
        assert_clean(default_app)

    def test_title_is_rendered(self, default_app):
        assert any("MARSWATER" in t.value for t in default_app.title)

    def test_recommendation_metrics_are_rendered(self, default_app):
        labels = [m.label for m in default_app.metric]
        assert "Recommended site" in labels
        assert "Population ceiling" in labels

    def test_ranking_and_scenario_tables_are_rendered(self, default_app):
        """Three tables: the ranking, the architecture comparison, the sweep."""
        assert len(default_app.dataframe) >= 3

    def test_analysis_sections_are_rendered(self, default_app):
        """AppTest cannot introspect Plotly figures, so check their headings."""
        headings = " ".join(h.value for h in default_app.subheader)
        assert "Predicted water-equivalent hydrogen" in headings
        assert "Site ranking" in headings
        assert "Where it breaks" in headings


class TestDashboardInteractions:
    def test_reports_the_breakpoint_at_a_large_population(self):
        """At 4,000 crew nothing is viable, and the app has to say why."""
        app = run_app(population=4000)
        assert_clean(app)
        messages = [w.value for w in app.warning] + [e.value for e in app.error]
        assert any("rock throughput" in m or "no shortlisted site" in m.lower()
                   for m in messages), messages

    def test_survives_the_smallest_outpost(self):
        """The unhappy paths must not raise on unguarded references."""
        assert_clean(run_app(population=10))

    def test_survives_disabling_propellant_production(self):
        assert_clean(run_app(propellant=False))

    def test_three_dimensional_views_are_rendered(self, default_app):
        headings = " ".join(h.value for h in default_app.subheader)
        assert "settlement this implies" in headings
        assert widget_by_label(
            default_app.slider, "Topographic exaggeration"
        ) is not None
