import sys
from io import xsf_info, el_info
from io import qe_out_info, make_qe_in
from io import init_log, upd_log
from io import init_axsf, upd_axsf
from mc import mc
import os
import numpy as np

xsf_filename = sys.argv[1] # read xsf filename from command line
el_list_filename = sys.argv[2] # read element list filename

# set simulation parameters
niter = 1500
max_disp = 0.05 # angstroms
T_move = 1 # kelvin
T_exc = T_move # temperature for exchange steps, use with caution
ry_ev = 13.605693009
buf_len = 2.0 # length above surface within which atoms can be added
#mu_list = [-1579.40 - 3, -428.07 - 3] # ti, o
mu_list = [0, 0] # ti, o

# get info from xsf file
xsf = xsf_info(xsf_filename) # instantiate xsf_info objects
xsf_old = xsf_info(xsf_filename)
xsf_new = xsf_info(xsf_filename)
xsf.get_lat_vec() # get lattice vectors
xsf.get_at_coord() # get atomic coordinates
xsf.get_el_list() # get list of element symbols
xsf.get_num_each_el() # get number of each element
xsf.get_c_min_max(buf_len) # get c values within which atom can be added
xsf.get_vol() # get volume of variable composition region
xsf.get_ind_rem_at() # get indices of removable atoms

el = el_info(el_list_filename) # instantiates el_info object
el.get_el_sym() # get element symbols
el.get_at_wt() # get atomic weights
el.get_therm_db(T_exc) # get thermal de Broglie wavelengths
el.get_ind_to_el_dict() # get index-to-element symbol dictionary
el.get_el_to_ind_dict() # get element symbol-to-index dictionary

# instantiate mc object
mc_test = mc(T_move, T_exc, max_disp, xsf)

# run mc simulation
os.system('mkdir -p temp') # make temp directory for qe calculations
os.chdir('temp') # enter temp
log_file = init_log('log.dat') # initialize log file
axsf_file = init_axsf('coord.axsf', niter, xsf) # initialize axsf file
for i in range(niter) :
    # makes a copy of xsf attributes called xsf_old
    xsf_old.copy(xsf)

    # attempt uvt action and store xsf attributes in xsf_new
    xsf_new.at_coord, \
        xsf_new.ind_rem_at, \
        xsf_new.el_list, \
        xsf_new.num_each_el, \
        xsf_new.num_at = mc_test.uvt_new_structure_np(xsf, el)
    
    # copy xsf_new attributes to xsf, try to figure out a way around this
    xsf.copy(xsf_new)

    # make input file
    make_qe_in('qe.in', xsf)
    
    # calculate and get total energy
    if xsf.num_at <= 2 :
        os.system('mpiexec.hydra -np 4 ../bin/pw.x -i qe.in > qe.out') # execute qe
    elif xsf.num_at <= 6 :
        os.system('mpiexec.hydra -np 9 ../bin/pw.x -i qe.in > qe.out')
    else :
        os.system('mpiexec.hydra -np 36 ../bin/pw.x -i qe.in > qe.out')
    qe_out = qe_out_info('qe.out')
    new_en = qe_out.get_final_en() * ry_ev # convert final energy from ry to ev

    # update T_exc
    mc_test.update_T_exc(T_move, T_exc, i, niter)

    # decide whether or not to accept uvt action, 
    accept = mc_test.uvt_mc(new_en, xsf, el, mu_list)

    # calculate free energy 
    free_en, _ = mc_test.get_free_g_p(new_en, xsf, el, mu_list)

    # if step not accepted, copy attributes from xsf_old to xsf
    if accept == 0 :
        xsf.copy(xsf_old)

    # write energies, number of accepted steps, and acceptance rate to log file
    upd_log(log_file, i, free_en, mc_test)

    # write atomic coordinates to axsf file
    upd_axsf(axsf_file, i, xsf)

log_file.close()
axsf_file.close()
os.chdir('../')
