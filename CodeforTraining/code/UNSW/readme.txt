------------------------------------------------------------------------------------------------------------- 
CITATION
------------------------------------------------------------------------------------------------------------- 

Please cite this data and code as:

H. Khamis, R. Weiss, Y. Xie, C-W. Chang, N. H. Lovell, S. J. Redmond, "QRS detection algorithm for telehealth electrocardiogram recordings," IEEE Transaction in Biomedical Engineering, vol. 63(7), p. 1377-1388, 2016. 

------------------------------------------------------------------------------------------------------------- 
DATABASE DESCRIPTION 
------------------------------------------------------------------------------------------------------------- 

The following description of the TELE database is from Khamis et al. (2016): 

"In Redmond et al (2012), 300 ECG single lead-I signals recorded in a telehealth environment are described. The data was recorded using the TeleMedCare Health Monitor (TeleMedCare Pty. Ltd. Sydney, Australia). This ECG is sampled at a rate of 500 Hz using dry metal Ag/AgCl plate electrodes which the patient holds with each hand; a reference electrode plate is also positioned under the pad of the right hand. Of the 300 recordings, 250 were selected randomly from 120 patients, and the remaining 50 were manually selected from 168 patients to obtain a larger representation of poor quality data. 

Three independent scorers annotated the data by identifying sections of artifact and QRS complexes. All scorers then annotated the signals as a group, to reconcile the individual annotations. Sections of the ECG signal which were less than 5 s in duration were considered to be part of the neighboring artifact sections and were subsequently masked. QRS annotations in the masked regions were discarded prior to the artifact mask and QRS locations being saved. 

Of the 300 telehealth ECG records in Redmond et al. (2012), 50 records (including 29 of the 250 randomly selected records and 21 of the 50 manually selected records) were discarded as all annotated RR intervals within these records overlap with the annotated artifact mask and therefore, no heart rate can be calculated, which is required for measuring algorithm performance. The remaining 250 records will be referred to as the TELE database." 


For all 250 recordings in the TELE database, the mains frequency was 50 Hz, the sampling frequency was 500 Hz and the top and bottom rail voltages were 5.556912223578890 and -5.554198887532222 mV respectively. 

------------------------------------------------------------------------------------------------------------- 
DATA FILE DESCRIPTION 
------------------------------------------------------------------------------------------------------------- 

Each record in the TELE database is stored as a X_Y.dat file where X indicates the index of the record in the TELE database (containing a total of 250 records) and Y indicates the index of the record in the original dataset containing 300 records (see Redmond et al. 2012). 

The .dat file is a comma separated values file. Each line contains: 
- the ECG sample value (mV) 
- a boolean indicating the locations of the annotated qrs complexes 
- a boolean indicating the visually determined mask 
- a boolean indicating the software determined mask (see Khamis et al. 2016) 

------------------------------------------------------------------------------------------------------------- 
CONVERTING DATA TO MATLAB STRUCTURE 
------------------------------------------------------------------------------------------------------------- 

A matlab function (readFromCSV_TELE.m) has been provided to read the .dat files into a matlab structure: 

%% 
% [DB,fm,fs,rail_mv] = readFromCSV_TELE(DATA_PATH) 
% 
% Extracts the data for each of the 250 telehealth ECG records of the TELE database [1] 
% and returns a structure containing all data, annotations and masks. 
% 
% IN: 	DATA_PATH - String. The path containing the .hdr and .dat files 
% 
% OUT: 	DB - 1xM Structure. Contains the extracted data from the M (250) data files. 
% 		The structure has fields: 
% 		* data_orig_ind - 1x1 double. The index of the data file in the original dataset of 300 records (see [1]) - for tracking purposes. 
% 		* ecg_mv - 1xN double. The ecg samples (mV). N is the number of samples for the data file. 
% 		* qrs_annotations - 1xN double. The qrs complexes - value of 1 where a qrs is located and 0 otherwise. 
% 		* visual_mask - 1xN double. The visually determined artifact mask - value of 1 where the data is masked and 0 otherwise. 
% 		* software_mask - 1xN double. The software artifact mask - value of 1 where the data is masked and 0 otherwise. 
% 	fm - 1x1 double. The mains frequency (Hz) 
% 	fs - 1x1 double. The sampling frequency (Hz) 
% 	rail_mv - 1x2 double. The bottom and top rail voltages (mV) 
% 
% If you use this code or data, please cite as follows: 
% 
% [1] H. Khamis, R. Weiss, Y. Xie, C-W. Chang, N. H. Lovell, S. J. Redmond, 
% "QRS detection algorithm for telehealth electrocardiogram recordings," 
% IEEE Transaction in Biomedical Engineering, vol. 63(7), p. 1377-1388, 
% 2016. 
% 
% Last Modified: 05/09/2016 
% 

------------------------------------------------------------------------------------------------------------- 
CALCULATING ARTIFACT MASKS – UNSW Artifact Detection Algorithm 
------------------------------------------------------------------------------------------------------------- 

A matlab function (UNSW_ArtifactMask.m) has been provided to compute the Rail Contact, High Frequency, Low Power, Baseline Shift and Final artifact masks described in Khamis et al. 2016: 

%% 
% [rcmask,hfmask,lpmask,bsmask,finalmask] = UNSW_ArtifactMask(rawecg,railV,fm,fs) 
% 
% Determines the ECG artifact mask as described in [1] 
% 
% IN: 	rawecg - 1xN double. The ECG samples (mV). N is the number of samples. 
% 	railV - 1x2 double. Bottom and top rail voltages (mV). 
% 	fm - 1x1 double. The mains frequency (Hz) 
% 	fs - 1x1 double. The sampling frequency (Hz) 
% 
% OUT: 	rcmask - 1xM1 double. M1 is the number of masked samples. Indices in rawecg of the rail contact mask - See RC Mask in [1]. 
% 	hfmask - 1xM2 double. M2 is the number of masked samples. Indices in rawecg of the high frequency mask - See HF Mask in [1]. 
% 	lpmask - 1xM3 double. M3 is the number of masked samples. Indices in rawecg of the low power mask - See LP Mask in [1]. 
% 	bsmask - 1xM4 double. M4 is the number of masked samples. Indices in rawecg of the baseline shift mask - See BS Mask in [1]. 
% 	finalmask - 1xM5 double. M5 is the number of masked samples. Indices in rawecg of the final mask - See Final Mask in [1]. 
% 
% 
% This function uses the files sortfilt1.m, medianfilter.mexw64 and 
% minmaxfilter.mexw64 - Ensure that these files are on the MATLAB path. 
% 
% If the .mexw64 files are incompatible with you version of MATLAB, please 
% rebuild the mex files from the corresponding .cpp and .h files provided. 
% 
% If you use this code or data, please cite as follows: 
% 
% [1] H. Khamis, R. Weiss, Y. Xie, C-W. Chang, N. H. Lovell, S. J. Redmond, 
% "QRS detection algorithm for telehealth electrocardiogram recordings," 
% IEEE Transaction in Biomedical Engineering, vol. 63(7), p. 1377-1388, 
% 2016. 
% 
% Last Modified: 05/09/2016 
% 

------------------------------------------------------------------------------------------------------------- 
DETECTING QRS LOCATIONS – UNSW QRS Detection Algorithm 
------------------------------------------------------------------------------------------------------------- 

A matlab function (UNSW_QRSDetector.m) has been provided which is an implementation of the QRS detector algorithm described in Khamis et al. 2016: 

%% 
% [qrs,RRlist,nRR,mRR,nSections] = UNSW_QRSDetector(rawecg,fs,mask,isplot) 
% 
% Determines the QRS locations in the raw ECG based on the UNSW QRS detection algorithm 
% 
% IN: 	rawecg - 1xN double. The ECG samples (mV). N is the number of samples. 
% 	fs - 1x1 double. The sampling frequency (Hz)- A vector of ECG amplitude. 
% 	mask - 1xM double. Indices of the artifact mask. 
% 	isplot - 1x1 boolean. True for ploting intermediate signals. False for no plotting. 
% 
% OUT: 	qrs - 1xQ double. Indices of the qrs locations. 
% 	RRlist - 1xR double. Indices of the RR-intervals in samples (not interupted by masking). 
% 	nRR - 1x1 double. The number of RR-intervals (not interupted by masking). 
% 	meanRR - 1x1 double. The mean RR interval in samples (not interupted by masking). 
% 	nSections - 1x1 double. The number of unmasked sections of ECG. 
% 
% 
% This function uses the files sortfilt1.m, medianfilter.mexw64 and 
% minmaxfilter.mexw64 - Ensure that these files are on the MATLAB path. 
% 
% If the .mexw64 files are incompatible with you version of MATLAB, please 
% rebuild the mex files from the corresponding .cpp and .h files provided. 
% 
% If you use this code or data, please cite as follows: 
% 
% [1] H. Khamis, R. Weiss, Y. Xie, C-W. Chang, N. H. Lovell, S. J. Redmond, 
% "QRS detection algorithm for telehealth electrocardiogram recordings," 
% IEEE Transaction in Biomedical Engineering, vol. 63(7), p. 1377-1388, 
% 2016. 
% 
% Last Modified: 05/09/2016 
% 

------------------------------------------------------------------------------------------------------------- 
REFERENCES 
------------------------------------------------------------------------------------------------------------- 

H. Khamis, R. Weiss, Y. Xie, C-W. Chang, N. H. Lovell, S. J. Redmond, "QRS detection algorithm for telehealth electrocardiogram recordings," IEEE Transaction in Biomedical Engineering, vol. 63(7), p. 1377-1388, 2016. 

S. J. Redmond, Y. Xie, D. Chang, J. Basilakis, and N. H. Lovell, "Electrocardiogram signal quality measures for unsupervised telehealth environments," Physiological Measurement, vol. 33, p. 1517, 2012. 