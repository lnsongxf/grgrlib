#!/bin/python2
# -*- coding: utf-8 -*-

directory = '/home/gboehl/repos/'
import os, sys, importlib
for i in os.listdir(directory):
    sys.path.append(directory+i)
sys.path.append('/home/gboehl/rsh/bs18/code/')

import numpy as np
import numpy.linalg as nl
import scipy.linalg as sl
import warnings
from grgrlib import *
from numba import njit

@njit(cache=True)
def preprocess(vals, ll_max = 5, kk_max 	= 30):

    N, J, A, IN, cx, dim_x, dim_y, b, x_bar, D  = vals

    dim_v   = dim_y - dim_x

    ss_max 	= ll_max + kk_max
    LL_mat 	= np.empty((ll_max,ss_max, dim_y,dim_y))
    SS_mat 	= np.empty((ll_max,kk_max, dim_x,dim_v))
    LL_term = np.empty((ll_max,ss_max, dim_y))
    SS_term = np.empty((ll_max,kk_max, dim_x))

    for ll in range(ll_max):
        for kk in range(kk_max):
            SS_mat[ll,kk], SS_term[ll,kk] 	= create_SS(vals[:7],ll,kk)
        for ss in range(ss_max):
            if ss >= ll-1: LL_mat[ll,ss], LL_term[ll,ss] 	= create_LL(vals[:7],ll,0,ss)

    return SS_mat, SS_term, LL_mat, LL_term

@njit(cache=True)
def create_SS(vals, l, k):
    N, J, A, IN, cx, dim_x, dim_y = vals
    N_k 		= nl.matrix_power(N.copy(),k)
    JN			= J @ N_k @ nl.matrix_power(A.copy(), l)
    temp3 		= subt(np.eye(dim_y), N_k)
    c_JN 		= J @ IN @ temp3 @ cx
    return -nl.inv(JN[:,:dim_x]) @ JN[:,dim_x:], -nl.inv(JN[:,:dim_x]) @ c_JN


@njit(cache=True)
def create_LL(vals, l, k, s):
    N, J, A, IN, cx, dim_x, dim_y = vals
    k0 		= max(s-l, 0)
    l0 		= min(l, s)
    N_k 		    = nl.matrix_power(N.copy(),k0)
    matrices 		= N_k @ nl.matrix_power(A.copy(),l0)
    subt_part       = subt(np.identity(dim_y), N_k)
    term			= IN @ subt_part @ cx
    return matrices, term

@njit(cache=True)
def LL_jit(l, k, s, v, vals):
    N, J, A, IN, cx, dim_x, dim_y = vals
    ## as in paper
    if k == 0:
        l = s
    k0 		= max(s-l, 0)
    l0 		= min(l, s)
    N_k 		    = nl.matrix_power(N.copy(),k0)
    matrices 		= N_k @ nl.matrix_power(A.copy(),l0)
    subt_part       = subt(np.identity(dim_y), N_k)
    term			= IN @ subt_part @ cx
    # return matrices @ np.hstack((SS_jit(vals[:7], l, k, v), v)) + term
    return matrices[:,:dim_x] @ SS_jit(vals[:7], l, k, v) + matrices[:,dim_x:] @ v + term

@njit(cache=True)
def SS_jit(vals, l, k, v):
    N, J, A, IN, cx, dim_x, dim_y = vals
    N_k 		= nl.matrix_power(N.copy(),k)
    JN			= J @ N_k @ nl.matrix_power(A.copy(),l)
    temp3 		= subt(np.eye(dim_y), N_k)
    c_JN 		= J @ IN @ temp3 @ cx
    return -nl.inv(JN[:,:dim_x]) @ JN[:,dim_x:] @ v - nl.inv(JN[:,:dim_x]) @ c_JN 

@njit(cache=True)
def LL_pp(l, k, s, v, precalc_mat):

    SS_mat, SS_term, LL_mat, LL_term     = precalc_mat

    dim_x   = SS_mat.shape[2]

    SS 	= SS_mat[l,k] @ v + SS_term[l,k]
    if not k:
        l = s
    matrices 	= LL_mat[l,s]
    term 		= LL_term[l,s]
    return matrices[:,:dim_x] @ SS + matrices[:,dim_x:] @ v + term


@njit(cache=True)
def boehlgorithm_pp(vals, v, precalc_mat):

    N, J, A, IN, cx, dim_x, dim_y, b, x_bar, D  = vals

    l, k 		= 0, 0
    l1, k1 		= 1, 1

    l_max   = precalc_mat[0].shape[0] - 1
    k_max   = precalc_mat[0].shape[1] 

    cnt     = 0
    while (l, k) != (l1, k1):
        cnt += 1
        l1, k1 		= l, k
        if l: l 		-= 1
        if cnt < 10e4:
            while b @ LL_pp(l, k, l, v, precalc_mat) - x_bar > 0:
                if l >= l_max:
                    l = 0
                    break
                l 	+= 1
        else:
            print('out')
            l = 0
        if (l) == (l1):
            if k: k 		-= 1
            while b @ LL_pp(l, k, l+k, v, precalc_mat) - x_bar < 0: 
                k +=1
                if k >= k_max:
                    print('k_max reached, exiting')
                    break

    v_new 	= LL_pp(l, k, 1, v, precalc_mat)[dim_x:]

    return v_new, (l, k)

@njit(cache=True)
def boehlgorithm_jit(vals, v, k_max = 20):

    N, J, A, IN, cx, dim_x, dim_y, b, x_bar, D  = vals
    
    l, k 		= 0, 0
    l1, k1 		= 1, 1

    cnt     = 0
    while (l, k) != (l1, k1):
        cnt += 1
        l1, k1 		= l, k
        if l: l -= 1
        if cnt < 10e4:
            while b @ LL_jit(l, k, l, v, vals[:7]) - x_bar > 0:
                if l > k_max:
                    l = 0
                    break
                l 	+= 1
        else:
            print('out')
            l   = 0
        if (l) == (l1):
            if k: k 		-= 1
            while b @ LL_jit(l, k, l+k, v, vals[:7]) - x_bar < 0: 
                k +=1
                if k > k_max:
                    print('k_max reached, exiting')
                    break

    v_new 	= LL_jit(l, k, 1, v, vals[:7])[dim_x:]

    return v_new, (l, k)

def boehlgorithm(model_obj, v):
    if hasattr(model_obj, 'precalc_mat'):
        return boehlgorithm_pp(model_obj.sys, v, model_obj.precalc_mat)
    else:
        return boehlgorithm_jit(model_obj.sys, v)


