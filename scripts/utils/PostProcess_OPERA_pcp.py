import os
import sys
sys.path.append('../libs/')
import h5py
import pyproj
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from LoadWriteData import LoadConfigFileFromYaml, build_dataset

obs = "OPERA_rain"
obs_filename_raw = "T_PASH22_C_EUOC_%Y%m%d%H%M%S.hdf"#old: 'ODC.LAM_%Y%m%d%H%M_000100.h5'

def make_dir_obs(obs, case):
    cwd = os.getcwd()
    os.chdir(f'../../OBSERVATIONS/')
    if os.path.exists(f'data_{obs}/') == False:
        os.mkdir(f'data_{obs}')
    os.chdir(f'data_{obs}/')
    if os.path.exists(f'{case}/') == False:
        os.mkdir(case)
        print(f'INFO: ../../OBSERVATIONS/data_{obs}/{case}/ directory created')
    os.chdir(cwd)
    obs_path = f'../../OBSERVATIONS/data_{obs}/{case}/'
    return obs_path

def get_vars_from_OPERA(filename, list_vars):
    # list_var must be a list with the "path" of the var join by ':' character
    print(f'INFO:reading {filename}')
    hf = h5py.File(filename, 'r')
    list_values = []
    for path in list_vars:
        groups, var = path.split(':')[:-1], path.split(':')[-1]
        grp = hf.get(groups[0])
        for group in groups[1:]:
            grp = grp.get(group)
        print(f'INFO:get {var} values')
        list_values.append(grp.get(var)[:].copy())
    hf.close()
    if len(list_values) == 1:
        return list_values[0]
    else:
        return list_values

def get_latlon2D_from_OPERA(filename):
    print(f'INFO:reading {filename}')
    hf = h5py.File(filename, 'r')
    # get projection params
    where = hf.get('where')
    projection = pyproj.Proj(where.attrs.get('projdef').decode())
    ll_lat = where.attrs.get('LL_lat')
    ll_lon = where.attrs.get('LL_lon')
    ur_lat = where.attrs.get('UR_lat')
    ur_lon = where.attrs.get('UR_lon')
    # transform lat-lon coordinates to meters
    ll_x, ll_y = projection(ll_lon, ll_lat)
    ur_x, ur_y = projection(ur_lon, ur_lat)
    # build grid in meters
    xi = np.linspace(int(np.round(ll_x, 0)), int(np.round(ur_x, 0)), where.attrs.get('xsize'))
    yi = np.linspace(int(np.round(ll_y, 0)), int(np.round(ur_y, 0)), where.attrs.get('ysize'))
    x, y = np.meshgrid(xi, yi)
    # reproject to lat-lon coordinates
    print(f'INFO:get lat-lon coordinates')
    lon2D, lat2D = projection(x, y, inverse = True)
    hf.close()
    return lat2D.copy(), lon2D.copy()

def main(path_OPERA_raw, case):
    # OBS data: database + variable
    obs_db, var_verif = obs.split('_')
    
    # observation database info
    config_obs = LoadConfigFileFromYaml(f'../../config/obs_db/config_{obs_db}.yaml')
    obs_filename = config_obs['format']['filename']
    obs_var_get = config_obs['vars'][var_verif]['var']

    # Case data: initial date + end date
    config_case = LoadConfigFileFromYaml(f'../../config/Case/config_{case}.yaml')
    date_ini = datetime.strptime(config_case['dates']['ini'], '%Y%m%d%H')
    date_end = datetime.strptime(config_case['dates']['end'], '%Y%m%d%H')

    obs_path = make_dir_obs(obs, case)
    
    dates = pd.date_range(date_ini, date_end, freq = '1h').to_pydatetime()
    for date in dates:
        file_obs = datetime.strftime(date, f'{path_OPERA_raw}{obs_filename_raw}')
        values = get_vars_from_OPERA(file_obs, [obs_var_get,])
        lat_obs, lon_obs = get_latlon2D_from_OPERA(file_obs)
        # ds = BuildXarrayDataset(np.flip(values, axis = 0), lon_obs, lat_obs, date, varName = var_verif, lonName = 'lon', latName = 'lat', descriptionNc = f'OPERA | 1-hour accumulated precipitation | {datetime.strftime(date - timedelta(hours = 1), "%Y%m%d%H")}-{datetime.strftime(date, "%Y%m%d%H")}')
        ds = build_dataset(
            np.flip(np.where(values == -8888000., 0.0, values), axis = 0),
            date,
            lat_obs,
            lon_obs,
            var_verif,
            attrs_var={
                "units": "mm",
                "long_name": "OPERA NIMBUS 1-hour accumulation composite",
                "_FillValue": "-9999000."
            }
        )
        file_new = datetime.strftime(date, f'{obs_path}{obs_filename}')
        print(f'INFO:saving processed values in {file_new}')
        ds.to_netcdf(
            file_new,
            encoding={"time": {"units": "seconds since 1970-01-01"}}
        )
    return 0

if __name__ == '__main__':
    main(str(sys.argv[1]), str(sys.argv[2]))