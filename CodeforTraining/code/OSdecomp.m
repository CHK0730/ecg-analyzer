function [xc, xq, Y, YOSc, YOSc2] = OSdecomp(x, locsf, p1, p2, EXT, GOS, K)

% EXT is used to determine the local trend.
% it is under the ASSUMPTION that the pattern is compactly supported
% or at least can be well approximated by compactly supported
% K is the number for nonlocal median

if nargin < 7
    K = 30 ;
end

if EXT < 0
    error('Q121')
end
p = p1+p2+1 ;
n = length(locsf) ;
Y = zeros(p, n) ;


p1e = p1 + EXT ; p2e = p2 + EXT ;
pe = p1e + p2e + 1 ;

% Primarily used to determine & remove the linear trend
X = [ones(pe,1) [-p1e:p2e]'] ;
Xb = X([1:EXT pe-EXT+1:pe], :) ;

for jj = 1: length(locsf)
    if locsf(jj)-p1e < 1
        tmp = x(1: locsf(jj)+p2e) ;
        tmp = [zeros(pe-length(tmp),1); tmp] ;
    else
        tmp = x(locsf(jj)-p1e: min(locsf(jj)+p2e, length(x))) ;
        if length(tmp) < pe
            tmp = [tmp; zeros(pe-length(tmp), 1)] ;
        end
    end

    q1 = p1 ; q2 = p2 ;
    if 1
        if jj > 1 && jj < length(locsf)
            q1 = round( (locsf(jj) - locsf(jj-1) + 1)*2/3 ) ;
            q2 = round( (locsf(jj+1) - locsf(jj) + 1)*2/3 ) ;
        end
    end

    if q2 < p2
        tmp(end-(p2-q2)+1: end) = 0 ;
    end

    if q1 < p1
        tmp(1:p1-q1) = 0 ;
    end

    if EXT > 0
        b = (Xb'*Xb) \ (Xb'*(tmp([1:EXT pe-EXT+1:pe])-median(tmp))) ;
        tmp = tmp - median(tmp) - X*b ;
    else
        tmp = tmp - median(tmp) ;
    end

    Y(:, jj) = tmp(EXT+1 : EXT+p) ;
end

YOSc = zeros(size(Y)) ;
YOSc2 = zeros(size(Y)) ;

if GOS

    fprintf('Run global OS \n')
    [YOSc, eta, r_p, k] = optimal_shrinkage_color(Y, 'fro', 1/2.01) ;
    disp([r_p k])

    [ind2, ~] = knnsearch(YOSc', YOSc', 'k', K) ;
    for ii = 1: size(Y, 2)
        YOSc2(:, ii) = median(Y(:, ind2(ii,:)), 2) ;
    end

else % LOS

    fprintf('Run ROSDOS \n')

    % run Roseland to determine neighbors
    knn = 50 ;

    [U, S] = roseland(Y, 0.75, 25, 0) ;
    Phi = transpose(U(:,2:end) * diag(S(2:end).^(0.5))) ;

    [ind, ~] = knnsearch(Phi(1:10,:)', Phi(1:10,:)', 'k', knn*4) ;

    for i = 1:n

        % traditional approach
        Yloc = Y(:, ind(i, 1:knn));  % local 1*knn neighbors from noisy data
        
        
        % now, carry out step 2 of ROSDOS
        Yloc = Phi(:, ind(i, :)) ;  % local 4*knn neighbors from noisy data
        [tmp, eta, r_p, k] = optimal_shrinkage_color(Yloc, 'fro', 1/2.01) ;
        
        [ind2, ~] = knnsearch(tmp', tmp(:, 1)', 'k', knn) ;
        YOSc2(:, i) = median(Y(:, ind(i, ind2)), 2) ;
        
    end
    

end


% stitch results (this is currently for pacemaker. Move to the main code later)
xq = zeros(size(x)) ;
xc = x ;
for jj = 1: length(locsf)
    if locsf(jj)-p1 < 1
        idx = 1: locsf(jj)+p2 ;
        tmp = YOSc2(p-length(idx)+1: p, jj) ;
    else
        idx = locsf(jj)-p1: min(locsf(jj)+p2, length(x)) ;
        tmp = YOSc2(1:length(idx), jj) ;
    end
    xc(idx) = xc(idx) - tmp ;
    xq(idx) = xq(idx) + tmp ;
end

