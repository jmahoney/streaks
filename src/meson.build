pkgdatadir = get_option('prefix') / get_option('datadir') / meson.project_name()
moduledir = pkgdatadir / 'streaks'
gnome = import('gnome')
python = import('python')

blueprints = custom_target('blueprints',
  input: files(
    'streaks/ui/window.blp',
    'streaks/ui/sidebar_row.blp',
    'streaks/ui/empty_view.blp',
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
  'streaks/window.py',
  'streaks/words.py'
)
install_data(streaks_sources, install_dir: moduledir)

streaks_widgets_sources = files(
  'streaks/widgets/__init__.py',
  'streaks/widgets/grid_widgets.py',
)
install_data(streaks_widgets_sources, install_dir: moduledir / 'widgets')

install_data(files('../data/style.css'), install_dir: pkgdatadir)
