import os, sys, platform, subprocess, shutil, zipfile

lib_posix_mapping = {
    'debug': 'win64_vc150d',
    'release': 'win64_vc150r'
} 

config_mapping = {
    'debug': 'Debug',
    'release': 'Release'
}

rt_config = 'MD'

if 'RUNTIME_CONFIG' in os.environ:
    rt_config = os.environ['RUNTIME_CONFIG']

def gen_static_lib_target(name, lib_path_prefix, conf):
    cmake_src = '''
add_library({&target} STATIC IMPORTED)
set_property(TARGET {&target} APPEND PROPERTY IMPORTED_CONFIGURATIONS DEBUG)
set_property(TARGET {&target} APPEND PROPERTY IMPORTED_CONFIGURATIONS RELEASE)
set_target_properties({&target} PROPERTIES 
    IMPORTED_LOCATION_DEBUG "${install_prefix}/lib/{&target_debug_lib}"
    IMPORTED_LOCATION_RELEASE "${install_prefix}/lib/{&target_release_lib}"
#    IMPORTED_LINK_INTERFACE_LANGUAGES_DEBUG "CXX"
    INTERFACE_INCLUDE_DIRECTORIES "${install_prefix}/include")
'''.replace('{&target}', name).replace('{&target_debug_lib}', conf['debug']).replace('{&target_release_lib}', conf['release'])
    return cmake_src

def gen_shared_lib_target(name, lib_path_prefix, conf):
    return '''
add_library({&target} SHARED IMPORTED)
set_property(TARGET {&target} APPEND PROPERTY IMPORTED_CONFIGURATIONS DEBUG)
set_property(TARGET {&target} APPEND PROPERTY IMPORTED_CONFIGURATIONS RELEASE)
set_target_properties({&target} PROPERTIES 
    IMPORTED_LOCATION_DEBUG "${install_prefix}/bin/{&target_debug_so}"
    IMPORTED_IMPLIB_DEBUG "${install_prefix}/lib/{&target_debug_lib}"
    IMPORTED_LOCATION_RELEASE "${install_prefix}/bin/{&target_release_so}"
    IMPORTED_IMPLIB_RELEASE "${install_prefix}/lib/{&target_release_lib}"
    INTERFACE_INCLUDE_DIRECTORIES "${install_prefix}/include"
)
'''.replace('{&target}', name).replace('{&target_debug_lib}', conf['debug']).replace('{&target_release_lib}', conf['release']) \
        .replace('{&target_debug_so}', conf['debugso']) \
        .replace('{&target_release_so}', conf['releaseso'])

def gen_host_exe_target(name, bin_path_prefix, conf):
    return '''
    add_executable({&target} IMPORTED)
    set_property(TARGET {&target} APPEND PROPERTY IMPORTED_CONFIGURATIONS RELEASE)
    set_target_properties({&target} PROPERTIES IMPORTED_LOCATION_RELEASE "${install_prefix}/bin/{&target_exe}")
'''.replace('{&target}', name).replace('{&target_exe}', conf['exe'])

target_type_action = {
    'shared_lib': gen_shared_lib_target,
    'static_lib': gen_static_lib_target,
    'program':    gen_host_exe_target,
}

def gen_cmake_package(path, pk_configs):
    cpf = open(path, 'w')
    cpf.write('get_filename_component(install_prefix "${CMAKE_CURRENT_LIST_DIR}" ABSOLUTE)\n')

    for item in pk_configs:
        item_name = item['name']
        item_type = item['type']
        item_conf = item['win64']
        cpf.write('if(WIN32)\n')
        cpf.write(target_type_action[item_type](item_name, 'lib', item_conf))
        cpf.write('\nendif(WIN32) # \n')
    cpf.close()

def copy_files_by_ext(file_dir, file_ext, target_dir):
    if not os.path.exists(target_dir):
        os.makedirs(target_dir)
    for _file in os.listdir(file_dir):
        if _file.endswith(file_ext):
            shutil.copyfile(os.path.join(file_dir, _file), os.path.join(target_dir, _file))

def copy_files(file_dir, target_dir):
    if not os.path.exists(target_dir):
        os.makedirs(target_dir)
    for _file in os.listdir(file_dir):
        real_path = os.path.join(file_dir, _file)
        target_path = os.path.join(target_dir, _file)
        if os.path.isdir(real_path):
            copy_files(real_path, target_path)
        elif os.path.isfile(real_path):
            shutil.copyfile(real_path, target_path)

def zipdir(path, ziph):
    for root, dirs, files in os.walk(path):
        for _file in files:
            ziph.write(os.path.join(root, _file), os.path.join(root[len(path)+1:], _file))

def build_x64(config, src, bld, ins):
    P = subprocess.Popen(['cmake', 
        '-GVisual Studio 15 2017 Win64',
        '-H{0}'.format(src),
        '-B{0}'.format(bld),
        '-DCMAKE_BUILD_TYPE={0}'.format(config_mapping[config]),
        '-DCMAKE_INSTALL_PREFIX={0}'.format(ins),
        '-DBENCHMARK_ENABLE_TESTING=OFF',
        '-Dprotobuf_BUILD_TESTS=OFF',
        '-Dprotobuf_BUILD_EXAMPLES=OFF',
        '-Dprotobuf_MSVC_STATIC_RUNTIME=OFF' if rt_config == 'MD' else '-Dprotobuf_MSVC_STATIC_RUNTIME=ON'
        ])
    P.wait()

    B = subprocess.Popen(['cmake',
        '--build', bld,
        '--config', config_mapping[config],
        '--target', 'install'
        ])
    B.wait()

pk_config = [
    {
        'name': 'protobuf',
        'platforms': ['win64'],
        'type': 'static_lib',
        'win64': 
        {
            'debug':    'win64_vc150d/libprotobufd.lib',
            'release':  'win64_vc150r/libprotobuf.lib',
        }
    },
    {
        'name': 'libprotoc',
        'platforms': ['win64'],
        'type': 'static_lib',
        'win64': 
        {
            'debug':    'win64_vc150d/libprotocd.lib',
            'release':  'win64_vc150r/libprotoc.lib',
        }
    },
    {
        'name': 'protoc',
        'platforms': ['win64'],
        'type': 'program',
        'win64': 
        {
            'exe': 'win64_vc150r/protoc.exe'
        }
    }
]

def build_win64(src, config):
    bld = os.path.join(src, '.build', 'win64' + rt_config.lower(), config)
    ins = os.path.join(src, '.build', 'artifacts', 'win64_' + rt_config.lower() + '_' + config)
    build_x64(config, os.path.join(src, 'cmake'), bld, ins)

def pack_win64():
    curdir = os.path.dirname(os.path.abspath(__file__))
    build_win64( curdir, 'debug' )
    build_win64( curdir, 'release' )
    artifacts_dir = os.path.join(curdir, 'output', '_tmp_' + rt_config.lower())
    copy_files(os.path.join(curdir, '.build', 'artifacts', 'win64_' + rt_config.lower() + '_debug', 'include'), os.path.join(artifacts_dir, 'include'))
    copy_files_by_ext(os.path.join(curdir, '.build', 'artifacts', 'win64_' + rt_config.lower() + '_debug', 'lib'), '.lib', os.path.join(artifacts_dir, 'lib', 'win64_vc150d'))
    copy_files_by_ext(os.path.join(curdir, '.build', 'artifacts', 'win64_' + rt_config.lower() + '_release', 'lib'), '.lib', os.path.join(artifacts_dir, 'lib', 'win64_vc150r'))
    copy_files_by_ext(os.path.join(curdir, '.build', 'artifacts', 'win64_' + rt_config.lower() + '_release', 'bin'), '.exe', os.path.join(artifacts_dir, 'bin', 'win64_vc150r'))
    gen_cmake_package(os.path.join(artifacts_dir, 'protobuf.cmake'), pk_config)
    archive_name = os.path.join(curdir, 'output', 'protobuf_{0}_windows.zip'.format(rt_config.lower()))
    zipf = zipfile.ZipFile(archive_name, 'w', zipfile.ZIP_DEFLATED)
    zipdir(artifacts_dir, zipf)
    zipf.close()
    
pack_win64()