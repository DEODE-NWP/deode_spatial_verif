#!/usr/bin/env python
# coding: utf-8

import os, sys
sys.path.append('scripts/libs/')
import re
import numpy as np
import cartopy.crs as ccrs
import matplotlib.pyplot as plt
import imageio.v2 as imageio
from datetime import datetime, timedelta
from glob import glob
from LoadWriteData import LoadConfigFileFromYaml, LoadPickle
from dicts import get_data_function, get_grid_function, colormaps
from times import lead_time_replace
from domains import set_domain_verif
from plots import PlotMapInAxis, plot_verif_domain_in_axis, plot_domain_in_axis
from colormaps import ecmwf_accum_pcp_cmap, ecmwf_accum_pcp_norm

# colors_name = ['tab:blue', 'tab:orange', 'tab:green', 'tab:red', 'tab:purple', 'tab:brown', 'tab:pink', 'tab:gray', 'tab:olive', 'tab:cyan']

def sorted_list_files(string):
    list_files = glob(string)
    list_files.sort()
    return list_files
    
def main(obs, case, exps):
    # OBS data: database + variable
    obs_db, var_verif = obs.split('_')

    # observation database info
    config_obs_db = LoadConfigFileFromYaml(f'config/obs_db/config_{obs_db}.yaml')
    obs_filename = config_obs_db['format']['filename']
    obs_fileformat = config_obs_db['format']['fileformat']
    if config_obs_db['vars'][var_verif]['postprocess'] == True:
        obs_var_get = var_verif
    else:
        obs_var_get = config_obs_db['vars'][var_verif]['var_raw']
    var_verif_description = config_obs_db['vars'][var_verif]['description']
    var_verif_units = config_obs_db['vars'][var_verif]['units']
    print(f'Load config file for {obs_db} database: \n file name: {obs_filename}; file format: {obs_fileformat}; var. to get: {obs_var_get}')

    # Case data
    config_case = LoadConfigFileFromYaml(f'config/Case/config_{case}.yaml')
    case_domain = config_case['location']['NOzoom']
    verif_domains = config_case['verif_domain']
    print(f'Map bounds: {case_domain}')
    
    # Experiments to compare between. Load fss to set common lead times
    configs_exps, lead_times_inits_exps = {}, {}
    expLowRes, expHighRes = exps.split('-VS-')
    for exp in (expLowRes, expHighRes):
        print(f'Load config file: config/exp/config_{exp}.yaml')
        configs_exps[exp] = LoadConfigFileFromYaml(f'config/exp/config_{exp}.yaml')
        lead_times_inits_exps[exp] = {}
        for init_time in configs_exps[exp]['inits'].keys():
            file_fss = f"pickles/FSS/{obs}/{case}/{exp}/FSS_{configs_exps[exp]['model']['name'].replace(' ', '').replace('.', '-')}_{exp}_{obs}_{init_time}.pkl"
            fss_scores = LoadPickle(file_fss)
            lead_times_inits_exps[exp][init_time] = tuple(fss_scores.keys())

    # common inits & lead_times
    mask_isin = np.isin(list(lead_times_inits_exps[expLowRes].keys()), list(lead_times_inits_exps[expHighRes].keys()))
    common_inits = np.array(list(lead_times_inits_exps[expLowRes].keys()))[mask_isin].copy()
    common_lead_times = {}
    for init_time in common_inits:
        mask_isin = np.isin(lead_times_inits_exps[expLowRes][init_time], lead_times_inits_exps[expHighRes][init_time])
        common_lead_times[init_time] = np.array(lead_times_inits_exps[expLowRes][init_time])[mask_isin]
        print(f'Set common lead times. {init_time}: {common_lead_times[init_time]}')

    values_databases = {}
    for iterator, init_time in enumerate(common_inits):
        date_exp_ini = datetime.strptime(init_time, '%Y%m%d%H')
        for db in (expLowRes, obs_db, expHighRes):
            values_databases[db] = []

        valid_times = []
        for lead_time in common_lead_times[init_time]:
            valid_time = date_exp_ini + timedelta(hours = int(lead_time))
            valid_times.append(valid_time)
            obs_file = valid_time.strftime(f'OBSERVATIONS/data_{obs}/{case}/{obs_filename}')
            obs_values, obs_lat, obs_lon = get_data_function[obs_fileformat](obs_file, [obs_var_get, 'lat', 'lon'])
            values_databases[obs_db].append(obs_values.copy())

            expLowRes_file = date_exp_ini.strftime(f"SIMULATIONS/{expLowRes}/data_regrid/{init_time}/{configs_exps[expLowRes]['model']['name'].replace(' ', '').replace('.', '-')}_{expLowRes}_{var_verif}_{obs_db}grid_{init_time}+{str(lead_time).zfill(2)}.nc")
            expLowRes_values, expLowRes_lat, expLowRes_lon = get_data_function['netCDF'](expLowRes_file, [var_verif, 'lat', 'lon'])
            values_databases[expLowRes].append(expLowRes_values.copy())

            expHighRes_file = date_exp_ini.strftime(f"SIMULATIONS/{expHighRes}/data_regrid/{init_time}/{configs_exps[expHighRes]['model']['name'].replace(' ', '').replace('.', '-')}_{expHighRes}_{var_verif}_{obs_db}grid_{init_time}+{str(lead_time).zfill(2)}.nc")
            expHighRes_values, expHighRes_lat, expHighRes_lon = get_data_function['netCDF'](expHighRes_file, [var_verif, 'lat', 'lon'])
            values_databases[expHighRes].append(expHighRes_values.copy())
            expHighRes_fileformat = lead_time_replace(configs_exps[expHighRes]['format']['filename'], int(lead_time))
            expHighRes_file_orig = date_exp_ini.strftime(f"SIMULATIONS/{expHighRes}/data_orig/{init_time}/{expHighRes_fileformat}")
            expHighRes_lat_orig, expHighRes_lon_orig = get_grid_function[configs_exps[expHighRes]['format']['fileformat']](expHighRes_file_orig)

            # set verif domain
            verif_domain = set_domain_verif(date_exp_ini + timedelta(hours = int(lead_time)), verif_domains)
            if verif_domain is None:
                verif_domain = [expHighRes_lon_orig[:, 0].max() + 0.5, expHighRes_lon_orig[:, -1].min() - 0.5, expHighRes_lat_orig[0, :].max() + 0.5, expHighRes_lat_orig[-1, :].min() - 0.5]
                print(f'verif domain not established for {datetime.strftime(date_simus_ini + timedelta(hours = lead_time.item()), "%Y%m%d%H")} UTC. By default: {verif_domain}')

            # Build the frame
            print(f'plotting {expLowRes_file} vs {obs_file} vs {expHighRes_file}')
            fig_frame = plt.figure(0, figsize = (36.0 / 2.54, 11.0 / 2.54), clear = True)
            for iterator_axis, array2D, lat2D, lon2D, sup_title, bool_left_label, bool_righ_label in zip(range(3), [expLowRes_values, obs_values, expHighRes_values], [expLowRes_lat, obs_lat, expHighRes_lat], [expLowRes_lon, obs_lon, expHighRes_lon], [f"{configs_exps[expLowRes]['model']['name']} [exp: {expLowRes}]", obs_db, f"{configs_exps[expHighRes]['model']['name']} [ exp: {expHighRes}]"], [True, False, False], [False, False, True]):
                ax = fig_frame.add_subplot(1, 3, iterator_axis + 1, projection = ccrs.PlateCarree())
                if iterator_axis == 1:
                    title_complete = f'{sup_title}\nValid on {valid_time.strftime("%Y-%m-%d at %Hz")}'
                else:
                    title_complete = f'{sup_title}\nRun: {init_time} UTC\nValid on {valid_time.strftime("%Y-%m-%d at %Hz")} (+{lead_time.zfill(2)})'
                ax, cbar = PlotMapInAxis(
                    ax = ax, 
                    data = array2D, 
                    lat = lat2D, 
                    lon = lon2D, 
                    extent = case_domain, 
                    title = title_complete, 
                    cb_label = f'{var_verif_description} ({var_verif_units})', 
                    left_grid_label = bool_left_label, 
                    right_grid_label = bool_righ_label, 
                    cmap = colormaps[var_verif]['map'], 
                    norm = colormaps[var_verif]['norm']
                )
                ax = plot_verif_domain_in_axis(ax, verif_domain, lat2D, lon2D)
            fig_frame.savefig(f"PLOTS/side_plots/plots_verif/gif_frames/{obs}/{case}/{exps.replace('-VS-', '_')}_{obs}_{init_time}+{lead_time.zfill(2)}.png", dpi = 300, bbox_inches = 'tight', pad_inches = 0.05)
            plt.close(0)
        
        # figure of total/max values
        fig = plt.figure(1, figsize = (36.0 / 2.54, 11.0 / 2.54), clear = True)
        if configs_exps[expLowRes]['vars'][var_verif]['accum']:
            valid_ini = valid_times[0] - timedelta(hours = 1) # TODO: accum_hours instead 1h. CAREFULLY
            lead_time_str_ini = str(int(common_lead_times[init_time][0]) - 1).zfill(2) # TODO: accum_hours instead 1h. CAREFULLY
        else:
            valid_ini = valid_times[0]
            lead_time_str_ini = common_lead_times[init_time][0]
        for iterator_axis, db, lat2D, lon2D, bool_left_label, bool_right_label in zip(range(3), list(values_databases.keys()), (expLowRes_lat, obs_lat, expHighRes_lat), (expLowRes_lon, obs_lon, expHighRes_lon), (True, False, False), (False, False, True)):
            ax = fig.add_subplot(1, 3, iterator_axis + 1, projection = ccrs.PlateCarree())
            if iterator_axis == 1:
                title = f'{db}\nValid from {valid_ini.strftime("%Y-%m %d-%Hz")} to {valid_times[-1].strftime("%d-%Hz")}'
            else:
                title = f"{configs_exps[db]['model']['name']} [exp: {db}]\nRun: {init_time} UTC\nValid from {valid_ini.strftime('%Y-%m %d-%Hz')} (+{lead_time_str_ini}) to {valid_times[-1].strftime('%d-%Hz')} (+{common_lead_times[init_time][-1]})"
            if var_verif == 'pcp':
                key = 'Total'
                values_to_plot = np.sum(values_databases[db], axis = 0)
                cb_label = f'{var_verif_description.replace("1", str(len(values_databases[db])))} ({var_verif_units})'
                cmap = ecmwf_accum_pcp_cmap # total pcp custom colorbar from ecmwf
                norm = ecmwf_accum_pcp_norm
            elif var_verif == 'bt':
                key = 'Min'
                values_to_plot = np.min(values_databases[db], axis = 0)
                cb_label = f'{key}. {var_verif_description} ({var_verif_units})'
                cmap = colormaps[var_verif]['map']
                norm = colormaps[var_verif]['norm']
            else:
                key = 'Max'
                values_to_plot = np.max(values_databases[db], axis = 0)
                cb_label = f'{key}. {var_verif_description} ({var_verif_units})'
                cmap = colormaps[var_verif]['map']
                norm = colormaps[var_verif]['norm']
            ax, cbar = PlotMapInAxis(
                ax = ax, 
                data = values_to_plot, 
                lat = lat2D, 
                lon = lon2D, 
                extent = case_domain, 
                title = title, 
                cb_label = cb_label, 
                left_grid_label = bool_left_label, 
                right_grid_label = bool_right_label, 
                cmap = cmap, 
                norm = norm
            )
            if len(verif_domains.keys()) == 1:
                ax = plot_verif_domain_in_axis(ax, verif_domain, lat2D, lon2D)
            if iterator_axis == 2:
                ax = plot_domain_in_axis(ax, expHighRes_lat_orig, expHighRes_lon_orig)
        fig.savefig(f"PLOTS/main_plots/{case}/{key}_{var_verif}_{case}_{exps.replace('-VS-', '_')}_{obs_db}_{init_time}+{lead_time_str_ini}_+{common_lead_times[init_time][-1]}.png", dpi = 600, bbox_inches = 'tight', pad_inches = 0.05)
        plt.close(1)
    
    # Build the GIF
    gif = []
    images_gif = sorted_list_files(f"PLOTS/side_plots/plots_verif/gif_frames/{obs}/{case}/{exps.replace('-VS-', '_')}_{obs}_*.png")
    for filename in images_gif:
        gif.append(imageio.imread(filename))
    imageio.mimsave(f"PLOTS/main_plots/{case}/{case}_{exps.replace('-VS-', '_')}_{obs}.gif", gif, duration = 0.5)
    return 0

if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2], sys.argv[3])
