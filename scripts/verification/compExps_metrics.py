#!/usr/bin/env python
# coding: utf-8

import sys
sys.path.append('scripts/libs/')
import numpy as np
import pandas as pd
import seaborn as sns
from glob import glob
from scipy.stats import wilcoxon
from matplotlib import pyplot as plt
from matplotlib.ticker import FormatStrFormatter
from matplotlib.lines import Line2D
from LoadWriteData import LoadConfigFileFromYaml, LoadPickle
from plots import PlotFSSInAxis, PlotSALinAxis, PlotViolinInAxis

def sorted_list_files(string):
    list_files = glob(string)
    list_files.sort()
    return list_files

def main(obs, case, exps):
    # OBS data: database + variable
    obs_db, var_verif = obs.split('_')

    # Experiments to compare between
    expLowRes, expHighRes = exps.split('-VS-')
    
    # Load results for FSS and SAL
    fss, sal = {}, {}
    for dictionary, stat in zip((fss, sal), ('FSS', 'SAL')):
        for exp in (expLowRes, expHighRes):
            config_exp = LoadConfigFileFromYaml(f'config/exp/config_{exp}.yaml')
            dictionary[exp] = {}
            for init_time in config_exp['inits'].keys():
                file_pickl = f"pickles/{stat}/{obs}/{case}/{exp}/{stat}_{config_exp['model']['name'].replace(' ', '').replace('.', '-')}_{exp}_{obs}_{init_time}.pkl"
                dictionary[exp][init_time] = LoadPickle(file_pickl)

    # common inits & lead times from FSS pickles
    mask_isin = np.isin(list(fss[expLowRes].keys()), list(fss[expHighRes].keys()))
    common_inits = np.array(list(fss[expLowRes].keys()))[mask_isin].copy()
    common_lead_times = {}
    for init_time in common_inits:
        mask_isin = np.isin(list(fss[expLowRes][init_time].keys()), list(fss[expHighRes][init_time].keys()))
        common_lead_times[init_time] = np.array(list(fss[expLowRes][init_time].keys()))[mask_isin]
        print(f'Set common lead times. {init_time}: {common_lead_times[init_time]}')
    
    # get thresholds and scales from FSS
    namecols_fss = fss[expLowRes][common_inits[0]][common_lead_times[common_inits[0]][0]].columns
    namerows_fss = fss[expLowRes][common_inits[0]][common_lead_times[common_inits[0]][0]].index

    # figure FSS mean
    fig = plt.figure(figsize = (19. / 2.54, 9. / 2.54), clear = True)
    for iterator, exp in zip(range(2), (expLowRes, expHighRes)):
        fss_scores = []
        for init_time in common_inits:
            for lead_time in common_lead_times[init_time]:
                fss_scores.append(fss[exp][init_time][lead_time].values.copy())
        ax = fig.add_subplot(1, 2, iterator + 1)
        PlotFSSInAxis(ax, pd.DataFrame(np.nanmean(fss_scores, axis = 0).round(2), columns = namecols_fss, index = namerows_fss), title = f'FSS plot | {exp} | {obs}', xLabel = 'Scale', yLabel = 'Threshold')
    fig.savefig(f"PLOTS/main_plots/{case}/Comparison_FSSmean_{obs}_{exps.replace('-VS-', '_vs_')}.png", dpi = 600, bbox_inches = 'tight', pad_inches = 0.05)
    plt.close()
    
    # figure FSS distribution
    with sns.axes_style('whitegrid'):
        fig = plt.figure(figsize=(19.0 / 2.54, 14.0 / 2.54), clear = True)
        fig.subplots_adjust(wspace = 0.45, hspace = 0.3)
        for iterator_row, namerow in enumerate(namerows_fss.values):
            for iterator_col, namecol in enumerate(namecols_fss.values):
                fss_exps_fixed_thresh_scale = {}
                for exp in (expLowRes, expHighRes):
                    values = []
                    index = []
                    for init_time in common_inits:
                        for lead_time in common_lead_times[init_time]:
                            values.append(fss[exp][init_time][lead_time].loc[namerow, namecol])
                            index.append(f'{init_time}+{lead_time}')
                    fss_exps_fixed_thresh_scale[exp] = pd.DataFrame(values, columns = [namecol], index = pd.Index(index))
                fss_comp_exps = pd.merge(fss_exps_fixed_thresh_scale[expLowRes], fss_exps_fixed_thresh_scale[expHighRes], left_index = True, right_index = True) # double check with common inits and lead times
                fss_comp_exps.rename(columns = {f'{namecol}_x': expLowRes, f'{namecol}_y': expHighRes}, inplace = True)
                
                ax = fig.add_subplot(len(namerows_fss), len(namecols_fss), iterator_row * len(namecols_fss) + iterator_col + 1)
                if ((iterator_col == 0) & (iterator_row == (len(namerows_fss) - 1))):
                    PlotViolinInAxis(ax, fss_comp_exps, xLabel = namecol, yLabel = namerow)
                elif iterator_col == 0:
                    PlotViolinInAxis(ax, fss_comp_exps, yLabel = namerow)
                elif iterator_row == (len(namerows_fss) - 1):
                    PlotViolinInAxis(ax, fss_comp_exps, xLabel = namecol)
                else:
                    PlotViolinInAxis(ax, fss_comp_exps)
                ax.set_yticks(np.arange(0.0, 1.25, 0.25))
                ax.tick_params(axis = 'x', length = 0.0, labelbottom = False)
                # if two data series are (not) statisticaly different --> green (red) contour
                try:
                    pValue = wilcoxon(fss_comp_exps.dropna()[expLowRes].values, fss_comp_exps.dropna()[expHighRes].values)[1] # pValue only allows two data series
                except ValueError:
                    pValue = None
                if pValue is not None:
                    print(f'{namerow} - {namecol} pValue: {pValue}')
                    if pValue < 0.05:
                        for index in (0, 1):
                            try:
                                ax.collections[index].set_edgecolor('tab:green')
                            except IndexError:
                                pass
                    else:
                         for index in (0, 1):
                            try:
                                ax.collections[index].set_edgecolor('tab:red')
                            except IndexError:
                                pass                   
        fig.suptitle(f'FSS distributions | {expLowRes} (left) - {expHighRes} (right) | {obs}', fontsize = 10)
        fig.savefig(f"PLOTS/main_plots/{case}/Comparison_FSSdist_{obs}_{exps.replace('-VS-', '_vs_')}.png", dpi = 600, bbox_inches = 'tight', pad_inches = 0.05)
        plt.close()
    
    # figure SAL all
    with sns.axes_style('darkgrid'):
        fig = plt.figure(figsize = (18. / 2.54, 8. / 2.54), clear = True)
        for iterator, exp in zip(range(2), (expLowRes, expHighRes)):
            ax = fig.add_subplot(1, 2, iterator + 1)
            sal_all_lead_times = pd.DataFrame()
            for init_time in common_inits:
                sal_all_lead_times = pd.concat([sal_all_lead_times.copy(), sal[exp][init_time]['values'].loc[common_lead_times[init_time]].copy()])
            if iterator == 1:
                bool_legend = True
                dict_params = {key: sal[exp][init_time]['detect_params'][key] for key in ('f', 'q', 'minsize', 'mindis')}
            else:
                bool_legend = False
                dict_params = {}
            PlotSALinAxis(ax, sal_all_lead_times.dropna()['Structure'].values, sal_all_lead_times.dropna()['Amplitude'].values, sal_all_lead_times.dropna()['Location'].values, title = f'SAL plot | {exp} | {obs}', detect_parms = dict_params, plotLegend = bool_legend)
        fig.savefig(f"PLOTS/main_plots/{case}/Comparison_SALall_{obs}_{exps.replace('-VS-', '_vs_')}.png", dpi = 600, bbox_inches = 'tight', pad_inches = 0.05)   
        plt.close()
    
    # figure SAL distribution
    with sns.axes_style('whitegrid'):
        fig = plt.figure(figsize=(14 / 2.54, 18.0 / 2.54), clear = True)
        for iterator, namecol in enumerate(['Structure', 'Amplitude', 'Location']):
            sal_exps_fixed_param = {}
            for exp in (expLowRes, expHighRes):
                sal_exps_fixed_param[exp] = pd.DataFrame()
                for init_time in common_inits:
                    common_index = [f'{init_time}+{lead_time}' for lead_time in common_lead_times[init_time]]
                    sal_exp_fixed_param_init = pd.DataFrame(sal[exp][init_time]['values'].loc[common_lead_times[init_time], namecol].values.copy(), columns = [exp], index = common_index)
                    sal_exps_fixed_param[exp] = pd.concat([sal_exps_fixed_param[exp].copy(), sal_exp_fixed_param_init.copy()])
            sal_comp_exps = pd.merge(sal_exps_fixed_param[expLowRes], sal_exps_fixed_param[expHighRes], left_index = True, right_index = True) # double check with common inits and lead times
            
            ax = fig.add_subplot(3, 1, iterator + 1)
            if iterator == 0:
                PlotViolinInAxis(ax, sal_comp_exps, title = f'SAL distributions | {" - ".join(sal_comp_exps.columns.values)} | {obs}', xLabel = '', yLabel = namecol, yLim = [-2, 2])
                ax.yaxis.set_major_formatter(FormatStrFormatter('%.1f'))
            elif namecol == 'Location':
                PlotViolinInAxis(ax, sal_comp_exps, yLabel = namecol, yLim = [0, 2])
            else:
                PlotViolinInAxis(ax, sal_comp_exps, yLabel = namecol, yLim = [-2, 2])
                ax.yaxis.set_major_formatter(FormatStrFormatter('%.1f'))
            # if two data series are (not) statisticaly different --> green (red) contour
            try:
                pValue = wilcoxon(sal_comp_exps.dropna()[expLowRes].values, sal_comp_exps.dropna()[expHighRes].values)[1] # pValue only allows two data series
            except ValueError:
                pValue = None
            if pValue is not None:
                print(f'{namecol} pValue: {pValue}')
                if pValue < 0.05:
                    for index in (0, 1):
                        try:
                            ax.collections[index].set_edgecolor('tab:green')
                        except IndexError:
                            pass
                else:
                     for index in (0, 1):
                        try:
                            ax.collections[index].set_edgecolor('tab:red')
                        except IndexError:
                            pass    
        fig.savefig(f"PLOTS/main_plots/{case}/Comparison_SALdist_{obs}_{exps.replace('-VS-', '_vs_')}.png", dpi = 600, bbox_inches = 'tight', pad_inches = 0.05)   
        plt.close()
    return 0

if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2], sys.argv[3])
