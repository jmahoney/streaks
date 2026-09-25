pkgdatadir = get_option('prefix') / get_option('datadir') / meson.project_name()
moduledir = pkgdatadir / 'streaks'
gnome = import('gnome')
python = import('python')

blueprints = custom_target('blueprints',
  input: files(
    'streaks/ui/window.blp',
    'streaks/ui/sidebar_row.blp',
    'streaks/ui/empty_view.blp',
    'streaks/ui/today_view.blp',
    'streaks/ui/catchup_banner.blp',
    'streaks/ui/checkin_card.blp',
    'streaks/ui/goal_row.blp',
    'streaks/ui/single_goal_row.blp',
    'streaks/ui/streak_dialog.blp',
    'streaks/ui/goal_edit_row.blp',
    'streaks/ui/stat_tile.blp',
    'streaks/ui/streak_view.blp',
    'streaks/ui/goal_bar_row.blp',
    'streaks/ui/run_row.blp',
    'streaks/ui/catchup_dialog.blp',
    'streaks/ui/catchup_row.blp',
    'streaks/ui/preferences_dialog.blp',
    'streaks/ui/shortcuts.blp',
  ),
  output: '.',
  command: [find_program('blueprint-compiler'), 'batch-compile', '@OUTPUT@', '@CURRENT_SOURCE_DIR@', '@INPUT@'],
)

gnome.compile_resources('streaks', 'streaks.gresource.xml',
  gresource_bundle: true, install: true, install_dir: pkgdatadir, dependencies: blueprints)

conf = configuration_data()
conf.set('PYTHON', python.find_installation('python3').full_path())
conf.set('VERSION', meson.project_version())
conf.set('localedir', get_option('prefix') / get_option('localedir'))
conf.set('pkgdatadir', pkgdatadir)
configure_file(input: 'com.cheerschopper.Streaks.in', output: 'com.cheerschopper.Streaks',
  configuration: conf, install: true, install_dir: get_option('bindir'), install_mode: 'r-xr-xr-x')

streaks_sources = files(
  'streaks/__init__.py',
  'streaks/__main__.py',
  'streaks/clock.py',
  'streaks/empty_view.py',
  'streaks/engine.py',
  'streaks/export.py',
  'streaks/main.py',
  'streaks/models.py',
  'streaks/resources.py',
  'streaks/settings.py',
  'streaks/sidebar_row.py',
  'streaks/state.py',
  'streaks/theme.py',
  'streaks/window.py',
  'streaks/goal_edit_row.py',
  'streaks/streak_dialog.py',
  'streaks/today_view.py',
  'streaks/catchup_banner.py',
  'streaks/checkin_card.py',
  'streaks/goal_row.py',
  'streaks/single_goal_row.py',
  'streaks/words.py',
  'streaks/stat_tile.py',
  'streaks/streak_view.py',
  'streaks/goal_bar_row.py',
  'streaks/run_row.py',
  'streaks/catchup_dialog.py',
  'streaks/catchup_row.py',
  'streaks/preferences_dialog.py',
)
install_data(streaks_sources, install_dir: moduledir)

streaks_widgets_sources = files(
  'streaks/widgets/__init__.py',
  'streaks/widgets/grid_widgets.py',
)
install_data(streaks_widgets_sources, install_dir: moduledir / 'widgets')

install_data(files('../data/style.css'), install_dir: pkgdatadir)
