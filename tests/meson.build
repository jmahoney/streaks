pytest = find_program('pytest', 'pytest-3', required: false)
if pytest.found()
  test_env = environment()
  test_env.set('STREAKS_GRESOURCE', meson.project_build_root() / 'src' / 'streaks.gresource')
  test_env.set('GSETTINGS_SCHEMA_DIR', meson.project_build_root() / 'data')
  test_env.set('GSETTINGS_BACKEND', 'memory')
  test_env.set('PYTHONPATH', meson.project_source_root() / 'src')
  test('unit', pytest, args: ['-q', meson.project_source_root() / 'tests' / 'unit'], env: test_env, timeout: 300)
  # GUI tests share one display, so they run serially; snapshot rendering runs in its own
  # process to keep window geometry out of the shared GSettings backend.
  test('gui', pytest, args: ['-q', meson.project_source_root() / 'tests' / 'gui', '--ignore=' + meson.project_source_root() / 'tests' / 'gui' / 'test_snapshots.py'], env: test_env, timeout: 600, is_parallel: false)
  test('snapshots', pytest, args: ['-q', meson.project_source_root() / 'tests' / 'gui' / 'test_snapshots.py'], env: test_env, timeout: 600, is_parallel: false)
endif
