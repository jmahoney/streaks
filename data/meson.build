desktop_file = i18n.merge_file(
  input: 'com.cheerschopper.Streaks.desktop.in',
  output: 'com.cheerschopper.Streaks.desktop',
  type: 'desktop',
  po_dir: '../po',
  install: true,
  install_dir: get_option('datadir') / 'applications'
)

test('Validate desktop file', find_program('desktop-file-validate'), args: [desktop_file])

appstream_file = i18n.merge_file(
  input: 'com.cheerschopper.Streaks.metainfo.xml.in',
  output: 'com.cheerschopper.Streaks.metainfo.xml',
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

gnome.compile_schemas(
  build_by_default: true,
  depend_files: 'com.cheerschopper.Streaks.gschema.xml'
)

test('Validate schema file', find_program('glib-compile-schemas'), args: ['--strict', '--dry-run', meson.current_source_dir()])

subdir('icons')
