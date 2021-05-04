'''
since we are randomly selected segments of each song in each epoch, 
the number of epochs is explosive so by a high probability, every entire song is accounted for. lol.
'''

import os
import sys
# sys.path.append(os.path.abspath('../..'))
sys.path.append(os.path.abspath(''))
sys.path.append(os.path.abspath('processing'))
print(sys.path)
import glob
import argparse
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import time

import torch
from torch import optim, nn
from torch.nn import functional as F
from torch.utils.data import DataLoader

import util
from util_method import save_model, load_model, plot_pred_against, plot_pred_comparison, standardize, windowing, reverse_windowing
### to edit accordingly.
from dataset import rdm_dataset as dataset_class
### to edit accordingly.
from networks import Three_FC_layer as archi

from ave_exp_by_prof import ave_exps_by_profile

#####################
####    Train    ####
#####################
def train(train_loader, model, test_loader, fold_i, args):
    
    
    loss_log = {
        'train_mse' : [],
        'train_r' : [],
        'test_mse' : [],
        'test_r' : []
    }
    '''
        intial round
    '''
    with torch.no_grad():
        model.eval()
        epoch_loss_log = {
            'mse' : [],
            'r' : []
        }
        for batchidx, (feature, label) in enumerate(train_loader):
            numbatches = len(train_loader)
            # Transfer to GPU
            feature, label = feature.to(device).float(), label.to(device).float()
            # clear gradients 
            optimizer.zero_grad()
            # forward pass
            output = model.forward(feature)
            output = output.squeeze(1)
            
            # MSE Loss calculation
            loss_mse = F.mse_loss(output, label)
            loss_r = pearson_corr_loss(output, label)

            epoch_loss_log['mse'].append(loss_mse.item())
            epoch_loss_log['r'].append(loss_r.item())
        
        aveloss_mse = np.average(epoch_loss_log['mse'])
        aveloss_r = np.average(epoch_loss_log['r'])
        print(f'Initial round without training || mse = {aveloss_mse:.2f} || r = {aveloss_r:.2f}')
        loss_log['train_mse'].append(aveloss_mse)
        loss_log['train_r'].append(aveloss_r)
    
    '''
        actual training
    '''
    n_epochs_least = 100
    n_epochs_stop = 50
    epochs_no_improve = 0
    min_val_loss = np.Inf
    early_stop = False

    for epoch in np.arange(args.num_epochs):
        # val_loss = 0 # for early stopping
        model.train()
        start_time = time.time()
        epoch_loss_log = {
            'mse' : [],
            'r' : []
        }

        for batchidx, (feature, label) in enumerate(train_loader):
            
            numbatches = len(train_loader)
            # Transfer to GPU
            feature, label = feature.to(device).float(), label.to(device).float()
            # print(feature.shape)
            # print('label: ', label)
            # clear gradients 
            optimizer.zero_grad()
            # forward pass
            output = model.forward(feature)
            # print('out: ', output)

            output = output.squeeze(1)
            # print(f'output stuffs: max: {output.max()} min: {output.min()} mean: {output.mean()} shape: {output.shape}')
            # print(f'label stuffs: max: {label.max()} min: {label.min()} mean: {label.mean()} shape: {label.shape}')
            torch.save(output, os.path.join(args.dir_path, 'saved_models', f'{args.model_name}', 'output'))
            torch.save(label, os.path.join(args.dir_path, 'saved_models', f'{args.model_name}', 'label'))
            
            # loss
            loss_mse = F.mse_loss(output, label)
            loss_r = pearson_corr_loss(output, label)
            # print('batchidx: ', batchidx)
            # print('pearson corr: ', loss_r)
            # print('loss_r.item(): ', loss_r.item())
            # if np.isnan(loss_r.item()):
            #     print('batchidx in if statement: ', batchidx)
            #     break
            loss = loss_mse*args.mse_weight + loss_r*args.r_weight
            
            # backward pass
            # loss.backward()
            loss_mse.backward()
            # update parameters
            optimizer.step()

            # record training loss
            epoch_loss_log['mse'].append(loss_mse.item())
            epoch_loss_log['r'].append(loss_r.item())

            print(f'Epoch: {epoch} || Batch: {batchidx}/{numbatches} || mse = {loss_mse.item():5f} || r = {loss_r.item():5f}', end = '\r')


            # val_loss += loss.item()
        
            # break
        # else:
            # continue
        
            
        # log average loss
        aveloss_mse = np.average(epoch_loss_log['mse'])
        aveloss_r = np.average(epoch_loss_log['r'])
        # print(f'Initial round without training || mse = {aveloss_mse:.2f} || r = {aveloss_r:.2f}')
        loss_log['train_mse'].append(aveloss_mse)
        loss_log['train_r'].append(aveloss_r)
        print(' '*200)

        epoch_duration = time.time() - start_time
        print(f'Fold: {fold_i} || Epoch: {epoch:3} || mse: {aveloss_mse:8.5f} || r: {aveloss_r:8.5f} || time taken (s): {epoch_duration:8f}')
        
        # test_ave_mse, test_ave_r, sum_test  = test(model, test_loader)
        test_ave_mse, test_ave_r  , _ = test(model, test_loader)

        loss_log['test_mse'].append(test_ave_mse)
        loss_log['test_r'].append(test_ave_r)

        

    # plot loss against epochs
    plt.plot(loss_log['train_mse'][1::], label='training loss mse')
    plt.plot(loss_log['test_mse'], label='test loss mse')
    plt.xlabel('epoch')
    plt.ylabel('loss')
    plt.legend()
    # plt.ylim([0, 0.5])
    plt.title(f"Loss || init mse:{loss_log['train_mse'][0]:.3f} | test mse: {test_ave_mse:.3f}")
    plt.savefig(os.path.join(args.dir_path, 'saved_models', f'{args.model_name}', f'loss_plot_fold{fold_i}_mse.png'))
    plt.close()

    plt.plot(loss_log['train_r'][1::], label='training loss r')
    plt.plot(loss_log['test_r'], label='test loss r')
    plt.xlabel('epoch')
    plt.ylabel('loss')
    # plt.ylim([-1, 1])
    plt.legend()
    plt.title(f"Loss || init r:{loss_log['train_r'][0]:.3f} | test r: {test_ave_r:.3f}")
    plt.savefig(os.path.join(args.dir_path, 'saved_models', f'{args.model_name}', f'loss_plot_fold{fold_i}_r.png'))
    plt.close()

    return model, aveloss_mse, aveloss_r, test_ave_mse, test_ave_r

####################
####    Test    ####
####################

def test(model, test_loader):

    model.eval()

    epoch_loss_log = {
            'mse' : [],
            'r' : []
        }
    with torch.no_grad():
        # model = load_model(model_name)
        for batchidx, (feature, label) in enumerate(test_loader):
            
            feature, label = feature.to(device).float(), label.to(device).float()
            # forward pass
            output = model(feature)
            output = output.squeeze(1)
            # MSE Loss calculation
            loss_mse = F.mse_loss(output, label)
            loss_r = pearson_corr_loss(output, label)
            # loss = loss_mse + loss_r
            # print(loss)
            epoch_loss_log['mse'].append(loss_mse.item())
            epoch_loss_log['r'].append(loss_r.item())
    
    test_ave_mse = np.average(epoch_loss_log['mse'])
    test_ave_r = np.average(epoch_loss_log['r'])
    # sum_test = test_ave_mse + abs(test_ave_r)
    sum_test = test_ave_mse + test_ave_r
    print(f'average test lost || mse: {test_ave_mse:4f} r: {test_ave_r:4f}')
    return test_ave_mse, test_ave_r, sum_test


def single_test(model, songurl, feat_dict, exps, fold_i, args, filename_prefix=None):
    '''
        exps - the original exps with many workers
    '''
    # print(songurl)
    # features - audio
    testfeat = feat_dict[songurl]
    # features - exps
    # labels
    all_exps_of_songurl_bool = exps['songurl']  == songurl
    all_exps_of_songurl = exps[all_exps_of_songurl_bool]
    # testlabel = exps.at[songurl,'labels']
    # print(all_exps_of_songurl)
    testlabels = all_exps_of_songurl['labels'].to_list()
    testprofiles = all_exps_of_songurl['profile'].to_list()
    # print(len(testfeat))
    # print(len(testlabel))

    # testinput_w = windowing(testfeat, args.lstm_size, step_size=args.lstm_size)
    
    c_fig, c_axs = plt.subplots(len(testprofiles),sharex=True)
    a_fig, a_axs = plt.subplots(len(testprofiles),sharex=True)
    c_fig.set_figheight(10)
    c_fig.set_figwidth(10)
    a_fig.set_figheight(10)
    a_fig.set_figwidth(10)


    for j in np.arange(len(testlabels)):

        # testlabel_w = windowing(testlabels[j], args.lstm_size, step_size=args.lstm_size)

        outputs = []
        loss_mse_list = []
        loss_r_list = []

        with torch.no_grad():
            
            profile = testprofiles[j]
            if hasattr(profile, '__iter__'):
                profile = list(profile)
            else:
                profile = [profile]
            # print(profile)

            testprofiles_repeat = [profile for a in np.arange(len(testlabels[j]))]
            # print(np.shape(testprofiles_repeat))
            # print(np.shape(testinput_w[i]))
            testinput = np.concatenate((testfeat, testprofiles_repeat),axis=1)
            
            # print(np.shape(testinput))
            # testlabel_i = testlabels[j]

            testinput = torch.from_numpy(testinput)
            testlabel = torch.from_numpy(testlabels[j])

            testinput = testinput.unsqueeze(0)
            testlabel = testlabel.unsqueeze(0)

            feature, label = testinput.to(device).float(), testlabel.to(device).float()
            # model = load_model(model, args.model_name, args.dir_path)

            # forward pass
            output = model(feature)
            output = output.squeeze(1)
            # MSE Loss calculation
            loss_mse = F.mse_loss(output, label)
            loss_mse_list.append(loss_mse.item())
            loss_r = pearson_corr_loss(output, label)
            loss_r_list.append(loss_r.item())
            # loss = loss_mse + loss_r

            output = output.squeeze()
            output = output.cpu().numpy()
            # output = np.atleast_1d(output)
            # https://stackoverflow.com/questions/35617073/python-numpy-how-to-best-deal-with-possible-0d-arrays
            # outputs.append(output)

        # print(loss.item())
        # output = reverse_windowing(outputs, args.lstm_size, step_size=args.lstm_size)

        dir_path = os.path.dirname(os.path.realpath(__file__))

        # temp_plot_c = plot_pred_comparison(output, testlabels[j], np.mean(loss_mse_list), np.mean(loss_r_list))
        c_axs[j].plot(output) #, label='prediction')
        c_axs[j].plot(testlabels[j]) #, label='ground truth')
        rloss = np.mean(loss_r_list)
        mseloss = np.mean(loss_mse_list)
        c_axs[j].set_title(f'mse: {mseloss:.5} || r: {rloss:.5}')
        c_axs[j].set_ylim([-1, 1])

        
        # temp_plot_a = plot_pred_against(output, testlabels[j])
        a_axs[j].scatter(testlabels[j], output, marker='x')
        

    c_fig.suptitle(f'{songurl}')
    c_fig.legend(['prediction', 'ground truth'])
    c_fig.savefig(os.path.join(dir_path, 'saved_models', f'{args.model_name}/predictions/{filename_prefix}{songurl}_prediction_fold_{fold_i}.png'))
    plt.close(c_fig)

    
    a_fig.suptitle(f'{songurl}')
    a_fig.savefig(os.path.join(dir_path, 'saved_models', f'{args.model_name}/predictions/{filename_prefix}{songurl}_y_vs_yhat_fold_{fold_i}.png'))
    plt.close(a_fig)



if __name__ == "__main__":
    
    ########################
    ####    Argparse    ####
    ########################

    dir_path = os.path.dirname(os.path.realpath(__file__))

    parser = argparse.ArgumentParser()
    parser.add_argument('--dir_path', type=str, default=dir_path)
    parser.add_argument('--affect_type', type=str, default='arousals', help='Can be either "arousals" or "valences"')
    parser.add_argument('--num_epochs', type=int, default=5)
    parser.add_argument('--model_name', type=str, default='hd512_mseonly_smooth1_testage', help='Name of folder plots and model will be saved in')
    parser.add_argument('--batch_size', type=int, default=8)
    parser.add_argument('--num_workers', type=int, default=10)
    parser.add_argument('--hidden_dim', type=int, default=512)
    parser.add_argument('--num_timesteps', type=int, default=30)
    # parser.add_argument('--step_size', type=int, default=1)
    parser.add_argument('--learning_rate', type=float, default=0.0001)
    parser.add_argument('--mse_weight', type=float, default=1.0)
    parser.add_argument('--r_weight', type=float, default=0.1)
    parser.add_argument('--conditions', nargs='+', type=str, default=['age'])
    # age, gender, master, country_enculturation, country_live, fav_music_lang, fav_genre, play_instrument, training, training_duration


    args = parser.parse_args()
    setattr(args, 'model_name', f'linear_{args.affect_type[0]}_p_{args.model_name}')
    print(args)

    # check if folder with same model_name exists. if not, create folder.
    os.makedirs(os.path.join(dir_path,'saved_models', args.model_name), exist_ok=True)
    os.makedirs(os.path.join(dir_path,'saved_models', args.model_name, 'predictions'), exist_ok=True)

    #########################
    ####    Load Data    ####
    #########################

    # read labels from pickle
    
    # exps = pd.read_pickle('data/exps_std_a_profile_ave.pkl')
    pinfo = util.load_pickle('data/pinfo_numero.pkl')
    original_exps = pd.read_pickle('data/exps_ready3.pkl')
    exps = ave_exps_by_profile(original_exps, pinfo, args.affect_type, args.conditions)
    # print(exps.head())
    
    ####################
    ####    Cuda    ####
    ####################

    # CUDA for PyTorch
    use_cuda = torch.cuda.is_available()
    device = torch.device("cuda:0" if use_cuda else "cpu")
    torch.manual_seed(42)
    torch.backends.cudnn.benchmark = True
    print('cuda: ', use_cuda)
    print('device: ', device)

    ####################
    ####    Loss    ####
    ####################

    def pearson_corr_loss(output, target, reduction='mean'):
        x = output
        y = target

        vx = x - x.mean(1).unsqueeze(-1) # Keep batch, only calcuate mean per sample
        vy = y - y.mean(1).unsqueeze(-1)

        cost = (vx * vy).sum(1) / (torch.sqrt((vx ** 2).sum(1)) * torch.sqrt((vy ** 2).sum(1)))
        cost[torch.isnan(cost)] = 0 #torch.tensor([0]).to(device)
        cost = cost*-1 
        # reducing the batch of pearson to either mean or sum
        if reduction=='mean':
            return cost.mean()
        elif reduction=='sum':
            return cost.sum()
        elif reduction==None:
            return cost

    ###########################
    ####    Dataloading    ####
    ###########################

    def dataloader_prep(feat_dict, exps, args):
        params = {'batch_size': args.batch_size,
            'shuffle': True,
            'num_workers': args.num_workers}
        # prepare data for testing
        
        dataset = dataset_class(feat_dict, exps, seq_len=args.num_timesteps)
        loader = DataLoader(dataset, **params)
        return loader

    '''
    5 FOLD CROSS VALIDATION LEGGO
    '''
    loss_log_folds = {'train_loss_mse':[], 'train_loss_r':[], 'test_loss_mse':[], 'test_loss_r':[]}
    num_folds = 1
    for fold_i in range(num_folds):


        ########################
        ####    Training    ####
        ########################

        # load the data 
        # read audio features from pickle
        train_feat_dict = util.load_pickle(f'data/folds/train_feats_{fold_i}.pkl')
        test_feat_dict = util.load_pickle(f'data/folds/test_feats_{fold_i}.pkl')
        
        train_loader = dataloader_prep(train_feat_dict, exps, args)
        test_loader = dataloader_prep(test_feat_dict, exps, args)

        ###########################
        ####    Model param    ####
        ###########################

        ## MODEL
        input_dim = list(train_feat_dict.values())[0].shape[1] + len(args.conditions) #724 # 1582 
        print('check input_dim: ', input_dim)
        model = archi(input_dim=input_dim, reduced_dim=args.hidden_dim).to(device)
        model.float()
        print(model)

        optimizer = torch.optim.Adam(model.parameters(), lr=args.learning_rate)
        
        model, train_ave_mse, train_ave_r, test_ave_mse, test_ave_r = train(train_loader, model, test_loader, fold_i, args)

        save_model(model, args.model_name, dir_path, f'{args.model_name}_{fold_i}')

        loss_log_folds['train_loss_mse'].append(train_ave_mse)
        loss_log_folds['train_loss_r']. append(train_ave_r)
        loss_log_folds['test_loss_mse'].append(test_ave_mse)
        loss_log_folds['test_loss_r']. append(test_ave_r)
        

        #######################
        ####    Testing    ####
        #######################

        # model = archi(input_dim).to(device)
        # model = load_model(model, args.model_name, dir_path)
        # test_ave_mse, test_ave_r, sum_test  = test(model, test_loader)

        for songurl in test_feat_dict.keys():
            single_test(model, songurl, test_feat_dict, exps, fold_i, args)

            
        print('mse')
        print(f'train loss list: {loss_log_folds["train_loss_mse"][0]:4f}')
        print(f'test loss list: {loss_log_folds["test_loss_mse"][0]:4f}')
        print('pcc')
        print(f'train loss list: {loss_log_folds["train_loss_mse"][0]:4f}')
        print(f'test loss list: {loss_log_folds["test_loss_mse"][0]:4f}')

    # logging

    args_dict = vars(args)
    # print(type(args_dict))
    # args_dict['num_epochs'] = num_epochs
    args_dict['tr_mse'] = f'{np.mean(loss_log_folds["train_loss_mse"]):.4f}'
    args_dict['tr_r'] = f'{np.mean(loss_log_folds["train_loss_r"]):.4f}'
    # args_dict['tr_loss'] = f'{train_ave_mse+train_ave_r:.4f}'

    args_dict['tt_mse'] = f'{np.mean(loss_log_folds["test_loss_mse"]):.4f}'
    args_dict['tt_r'] = f'{np.mean(loss_log_folds["test_loss_r"]):.4f}'
    # args_dict['tt_loss'] = f'{sum_test:.4f}'

    args_dict.pop('dir_path')
    # print(args_dict)
    args_series = pd.Series(args_dict)
    args_df = args_series.to_frame().transpose()
    # print(args_df)

    exp_log_filepath = os.path.join(dir_path,'saved_models','experiment_log_linear1.pkl')
    if os.path.exists(exp_log_filepath):
        exp_log = pd.read_pickle(exp_log_filepath)
        exp_log = exp_log.append(args_df).reset_index(drop=True)
        pd.to_pickle(exp_log, exp_log_filepath)
        print(exp_log)
    else:
        pd.to_pickle(args_df, exp_log_filepath)
        print(args_df)