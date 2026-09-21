"""The streak history content pane: stat tiles, activity chart, and per-goal/earlier-run
breakdowns (design-spec §4).

No engine/database logic lives here beyond picking which run/range the chart currently shows —
every string, number and cell colour rendered comes straight from ``engine.history()``.
"""

from __future__ import annotations

import gettext

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, GObject, Gtk

from streaks import engine, theme
from streaks.engine import StreakData
from streaks.goal_bar_row import StreaksGoalBarRow  # noqa: F401  registers $StreaksGoalBarRow
from streaks.run_row import StreaksRunRow  # noqa: F401  registers $StreaksRunRow
from streaks.stat_tile import StreaksStatTile  # noqa: F401  registers $StreaksStatTile
from streaks.state import AppState
from streaks.widgets.grid_widgets import HeatmapWidget  # noqa: F401  registers $HeatmapWidget

_ = gettext.gettext


@Gtk.Template(resource_path="/com/cheerschopper/Streaks/streaks/ui/streak_view.ui")
class StreaksStreakView(Adw.Bin):
    """The streak history content pane. Call ``set_state()`` then ``configure()`` before it
    renders anything."""

    __gtype_name__ = "StreaksStreakView"

    __gsignals__ = {
        "catch-up": (GObject.SignalFlags.RUN_FIRST, None, (int,)),
    }

    tile_running = Gtk.Template.Child()
    tile_unconfirmed = Gtk.Template.Child()
    tile_confirmed = Gtk.Template.Child()
    tile_hit = Gtk.Template.Child()
    chart_title_label = Gtk.Template.Child()
    best_label = Gtk.Template.Child()
    chart_caption_label = Gtk.Template.Child()
    range_toggle = Gtk.Template.Child()
    day_labels_box = Gtk.Template.Child()
    heatmap = Gtk.Template.Child()
    legend_box = Gtk.Template.Child()
    legend_entries_box = Gtk.Template.Child()
    catch_up_link = Gtk.Template.Child()
    goals_card = Gtk.Template.Child()
    goal_bars_list = Gtk.Template.Child()
    runs_card = Gtk.Template.Child()
    runs_list = Gtk.Template.Child()

    streak_id = GObject.Property(type=int, default=0)

    def __init__(self, **kwargs):
        """Initialize the view. It renders nothing until ``set_state()``/``configure()``."""
        super().__init__(**kwargs)
        self.state: AppState | None = None
        self._streak: StreakData | None = None
        self._run_index: int | None = None
        self._legend: list[tuple[str, str | None, str]] = []

        # The legend swatches carry resolved colours, so repaint them when the scheme flips.
        theme.watch(self, lambda: self._rebuild_legend(self._legend))
        self.range_toggle.connect("notify::active-name", self._on_range_changed)
        self.runs_list.connect("row-activated", self._on_run_activated)
        self.catch_up_link.connect("clicked", self._on_catch_up_clicked)

    # -- wiring -----------------------------------------------------------------

    def set_state(self, state: AppState) -> None:
        """Bind to ``state`` (needed for ``today()``/settings before ``configure()``)."""
        self.state = state

    def configure(self, streak: StreakData) -> None:
        """Show ``streak``'s history, resetting back to "this run" mode."""
        self.streak_id = streak.id
        self._streak = streak
        self._run_index = None
        self.range_toggle.set_active_name("run")
        self._rebuild()

    # -- rebuilding ---------------------------------------------------------------

    @staticmethod
    def _clear_listbox(listbox: Gtk.ListBox) -> None:
        row = listbox.get_row_at_index(0)
        while row is not None:
            listbox.remove(row)
            row = listbox.get_row_at_index(0)

    @staticmethod
    def _clear_box(box: Gtk.Box) -> None:
        child = box.get_first_child()
        while child is not None:
            nxt = child.get_next_sibling()
            box.remove(child)
            child = nxt

    def _rebuild(self) -> None:
        if self.state is None or self._streak is None:
            return

        today = self.state.today()
        settings = self.state.settings.to_engine()
        lifetime = self.range_toggle.get_active_name() == "lifetime"
        run_index = None if lifetime else self._run_index
        hist = engine.history(self._streak, today, settings, run_index=run_index, lifetime=lifetime)

        tiles = (self.tile_running, self.tile_unconfirmed, self.tile_confirmed, self.tile_hit)
        for tile, (value, caption, style) in zip(tiles, hist.tiles, strict=True):
            tile.configure(value, caption, style)

        self.chart_title_label.set_label(hist.chart_title)
        self.best_label.set_visible(hist.is_best)

        run_toggle = self.range_toggle.get_toggle_by_name("run")
        if run_toggle is not None:
            if not lifetime and self._run_index is not None:
                run_toggle.set_label(_("Run %(idx)d") % {"idx": self._run_index})
            else:
                run_toggle.set_label(_("This run"))

        self._rebuild_day_labels(hist.day_labels)
        self.heatmap.set_cells([cell for week in hist.weeks for cell in week])

        self._rebuild_legend(hist.legend)

        self.catch_up_link.set_visible(hist.catch_up_link is not None)
        if hist.catch_up_link is not None:
            self.catch_up_link.set_label(hist.catch_up_link)

        self._rebuild_goal_bars(hist.goal_bars)
        self._rebuild_earlier_runs(hist.earlier_runs)

    def _rebuild_day_labels(self, day_labels: list[str]) -> None:
        self._clear_box(self.day_labels_box)
        for label in day_labels:
            widget = Gtk.Label(label=label)
            widget.set_xalign(0)
            widget.set_size_request(-1, 13)
            widget.set_valign(Gtk.Align.CENTER)
            widget.add_css_class("chart-day-label")
            self.day_labels_box.append(widget)

    def _rebuild_legend(self, legend: list[tuple[str, str | None, str]]) -> None:
        self._legend = legend
        self._clear_box(self.legend_entries_box)
        for fill, border, label in legend:
            entry = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
            entry.set_valign(Gtk.Align.CENTER)

            swatch = Gtk.Box()
            swatch.set_size_request(11, 11)
            swatch.set_valign(Gtk.Align.CENTER)
            swatch.add_css_class("chart-legend-swatch")
            provider = Gtk.CssProvider()
            border_css = (
                f"border: 1px solid {theme.resolve(border)};" if border else "border: none;"
            )
            provider.load_from_string(
                f"* {{ background-color: {theme.resolve(fill)}; {border_css} }}"
            )
            swatch.get_style_context().add_provider(
                provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
            )
            entry.append(swatch)

            caption = Gtk.Label(label=label)
            caption.add_css_class("caption")
            caption.add_css_class("dim-label")
            entry.append(caption)

            self.legend_entries_box.append(entry)

    def _rebuild_goal_bars(self, goal_bars: list[tuple[str, float, str, bool]]) -> None:
        self._clear_listbox(self.goal_bars_list)
        for name, ratio, ratio_text, low in goal_bars:
            row = StreaksGoalBarRow()
            row.configure(name, ratio, ratio_text, low)
            self.goal_bars_list.append(row)

    def _rebuild_earlier_runs(
        self, earlier_runs: list[tuple[str, str, list[engine.Cell], int]]
    ) -> None:
        self._clear_listbox(self.runs_list)
        self.runs_card.set_visible(bool(earlier_runs))
        for title, meta, cells, idx in earlier_runs:
            row = StreaksRunRow()
            row.configure(title, meta, cells, idx)
            self.runs_list.append(row)

    # -- interactions ---------------------------------------------------------------

    def _on_range_changed(self, *_args) -> None:
        self._run_index = None
        self._rebuild()

    def _on_run_activated(self, _listbox: Gtk.ListBox, row: StreaksRunRow) -> None:
        target_index = row.run_index
        if self.range_toggle.get_active_name() != "run":
            self.range_toggle.set_active_name("run")
        self._run_index = target_index
        self._rebuild()

    def _on_catch_up_clicked(self, _button: Gtk.Button) -> None:
        self.emit("catch-up", self.streak_id)
