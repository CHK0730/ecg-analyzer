function [Y_os,eta,r_p,k] = optimal_shrinkage_color(Y,loss,c) 
% Algorithm 1 in "Data-Driven optimal shrinkage of singular values under high-dimensional noise with separable covariance structure with application"
%=========input====================
% Y : Noisy data matrix;
% Assume Y = S+Z. S is the clean data matrix with finite low rank r and Z is the matrix with only noise.
% loss: 'fro', 'op', ,'op2', 'nuc'. Each loss corresponds to different optimal shrinkers.
% 'fro' - optimal shrinkers for Frobenius norm loss 
% 'op' - orginal optimal shrinkers for operater norm loss derived in "Optimal
%        Shrinkage of Singular Values", Gavish & Donoho 2014
% 'op2' - optimal shrinkers for operater norm loss derived in "Optimal
%         singular value shrinkage for operator norm loss" Leeb 2020
% 'nuc' - optimal shrinkers for nuclear norm loss
%
%  c: a constant selected from (0, 1/2). Check Theorem 4.2 and the end of
%  Section 4 in the original paper for detail about how to select c.
%  Default c = 1/2.1 to ensure n^c >> r.
%
%=========output===================
% Y_os_out: denoised matrix
% eta_out: shrinked singular values
% r_p_out: estimated effective rank
% Pei-Chun Su, 04/05/2023
%==================================
% 

% Set the input matrix to be a p-by-n matrix with p<=n.

% Deafualt c
if nargin < 3
    c = 1/2.01;
end

[p,n] = size(Y); 
transpose = 0;
if p>n
    Y = Y';
    transpose = 1;
end
[p,n] = size(Y);
[U,s,V] = svd(Y,'econ');
s = diag(s);

u = [s.^2; zeros(n-p, 1)] ;
lab = s.^2 ;


% Compute eigenvalues of YY' and Y'Y
%u = eig(Y'*Y); 
u = sort(u,'descend');
%lab = eig(Y*Y'); 
lab = sort(lab,'descend');
% Compute the estimated bulk edge in equation (41)
k = floor(p^(c));


lambda_p = lab(k+1)+ 1/(2^(2/3)-1) * (lab(k+1)-lab(2*k+1)); % Estimated bulk edge

% Compute the estimated effective rank in equation (42)
r_p = sum(lab/lambda_p-1 > p^(-1/3));
% Compute the estimated distribution of ZZ' in equation (44)
sr = s((r_p+1):end);
fZ = createPseudoNoise(sr,k,'i'); 
fZ = fZ.^2;
e = 1;
while e
    % If the first eigenvalues of fZ and fZ2 are not similar,
    % increase k
    fZ2 = createPseudoNoise(sr,k+1,'i'); 
    fZ2 = fZ2.^2;
    if abs(fZ(1)/fZ2(1)-1)>p^(-1/3)
        k = k+1;
        fZ = fZ2;
        lambda_p = lab(k+1)+ 1/(2^(2/3)-1) * (lab(k+1)-lab(2*k+1));
        r_p = sum(lab/lambda_p-1 > p^(-1/3));
    else 
        e = 0;
    end
end

ov = lab(1:r_p); % Outlier eigenvecotrs of YY' and Y'Y
eta = zeros(1,length(lab)); % array of estimated optimal shrinkers

for j = 1:r_p

    %compute estimated Transforms. Check equations (48)-(50)
    m1 = (1/(p-r_p) *sum(1./(fZ(1:end)-ov(j))));
    dm1 = (1/(p-r_p) *sum(1./(fZ(1:end)-ov(j)).^2));
    m2 = -(1-(p)/(n))/ov(j) + m1*(p)/(n);
    dm2 = (1-(p)/(n))/(ov(j)^2) + dm1*(p)/(n);
    dTau = m1*m2 + ov(j)*dm1*m2 + ov(j)*m1*dm2;
    d = 1/sqrt(ov(j)*m1*m2);
    a1 = abs(m1/(d^2*dTau)); a2 = (m2/(d^2*dTau));
    
    %Compute optial shrinkers in equation (52)
    if loss == "fro"
        eta(j) = d*sqrt(a1*a2);
    elseif loss == "op"
        eta(j) = d;
    elseif loss == "op2"
        eta(j) = d*sqrt(min(a1,a2)/max(a1,a2));
    elseif loss == "nuc"
        eta(j) = abs(d*(sqrt(a1*a2)- sqrt((1-a1)*(1-a2))));
    end
   

end

% Compute denoised matrix 
Y_os = U*diag(eta)*V(:,1:p)';
if transpose
    Y_os = Y_os';
end
end

