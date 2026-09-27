app_conf = configuration_data()
app_conf.set('APPLICATION_ID', application_id)
app_conf.set('bindir', get_option('prefix') / get_option('bindir'))

desktop_file = i18n.merge_file(
  input: configure_file(
    input: 'com.cheerschopper.Streaks.desktop.in',
    output: application_id + '.desktop.in',
    configuration: app_conf,
  ),
  output: application_id + '.desktop',
  type: 'desktop',
  po_dir: '../po',
  install: true,
  install_dir: get_option('datadir') / 'applications'
)

test('Validate desktop file', find_program('desktop-file-validate'), args: [desktop_file])

appstream_file = i18n.merge_file(
  input: configure_file(
    input: 'com.cheerschopper.Streaks.metainfo.xml.in',
    output: application_id + '.metainfo.xml.in',
    configuration: app_conf,
  ),
  output: application_id + '.metainfo.xml',
  type: 'xml',
  po_dir: '../po',
  install: true,
  install_dir: get_option('datadir') / 'metainfo'
)

test('Validate appstream file', find_program('appstreamcli'), args: ['validate', '--no-net', '--explain', appstream_file])

install_data(
  'com.cheerschopper.Streaks.gschema.xml',
  install_dir: get_option('datadir') / 'glib-2.0' / 'schemas'
)

# The desktop file declares DBusActivatable=true, so Flatpak export requires a matching D-Bus
# service file.
configure_file(
  input: 'com.cheerschopper.Streaks.service.in',
  output: application_id + '.service',
  configuration: app_conf,
  install: true,
  install_dir: get_option('datadir') / 'dbus-1' / 'services'
)

gnome.compile_schemas(
  build_by_default: true,
  depend_files: 'com.cheerschopper.Streaks.gschema.xml'
)

test('Validate schema file', find_program('glib-compile-schemas'), args: ['--strict', '--dry-run', meson.current_source_dir()])

subdir('icons')
