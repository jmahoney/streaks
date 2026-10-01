project('streaks', version: '0.3.0', license: 'MIT', meson_version: '>= 1.0.0', default_options: ['warning_level=2'])
i18n = import('i18n')
gnome = import('gnome')

base_id = 'com.cheerschopper.Streaks'
profile = get_option('profile')
# Development builds (GNOME Builder) get their own app ID, and with it their own sandbox data,
# settings and D-Bus name, so they never touch the installed app's database.
application_id = profile == 'development' ? base_id + '.Devel' : base_id
subdir('data')
subdir('src')
subdir('po')
subdir('tests')
gnome.post_install(glib_compile_schemas: true, gtk_update_icon_cache: true, update_desktop_database: true)
