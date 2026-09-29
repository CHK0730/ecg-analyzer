function [xq, CHECK] = stitchALL(Y, locsf, N, p1)

xq = zeros(N, 1) ;
CHECK = zeros(N, 1) ;
[p, n] = size(Y) ;
p2 = p - p1 - 1 ; % p2 right, p1 left
%disp([p n N p1 p2])

FACTOR1 = 4/5 ;

flag1 = [] ;
flag2 = [] ;




% No need to modify the LHS of the first beat
WWl = ones(p1, 1) ; 

for jj = 1: length(locsf)-1
    tmpc = Y(:, jj) ;
    tmpCHECK = ones(p, 1) ;

    % WHEN there is an overlap, modify the boundaries of tmpc/tmpCHECK for the stitch
    % by constructing the weight!
    % 3 cases to consider!!!!

    % modify LHS: use the previous beat's construction
    tmpc(1:p1) = tmpc(1:p1) .* WWl ;
    tmpCHECK(1:p1) = tmpCHECK(1:p1) .* WWl ;
    clear WWl ;

    % construct RHS(j) weight and LHS(j+1) weight
    if locsf(jj)+p2 > locsf(jj+1)-p1
        
        Qlen2 = ceil((locsf(jj+1) - locsf(jj)) * FACTOR1) ;

        % if RHS(j) is too long but LHS(j+1) is okay, use LHS(j+1)
        if p2 > Qlen2 && p1 <= Qlen2 
            flag1 = [flag1 jj] ;
            p2tmp = Qlen2 ;
            OVERLAP = (locsf(jj)+p2tmp) - (locsf(jj+1)-p1) + 1 ;
            WWr = zeros(p2, 1) ;
            WWr(1:p2tmp) = 1 ;
            if OVERLAP > 0
                WWr(p2tmp-OVERLAP+1: p2tmp) = cos(linspace(0,pi/2,OVERLAP)').^2 ;
            end

            WWl = ones(p1, 1) ;
            if OVERLAP > 0
                WWl(1: OVERLAP) = sin(linspace(0,pi/2,OVERLAP)').^2 ;
            end


        % if both RHS(j) and LHS(j+1) are too long, manually decide
        elseif p2 > Qlen2 && p1 > Qlen2 
            flag1 = [flag1 jj] ;
            p2tmp = Qlen2 ;
            p1tmp = Qlen2 ;
            OVERLAP = (locsf(jj)+p2tmp) - (locsf(jj+1)-p1tmp) + 1 ;
            WWr = zeros(p2, 1) ;
            WWr(1:p2tmp) = 1 ;
            if OVERLAP > 0
                WWr(p2tmp-OVERLAP+1: p2tmp) = cos(linspace(0,pi/2,OVERLAP)').^2 ;
            end

            WWl = zeros(p1, 1) ;
            WWl(end-p1tmp+1:end) = 1 ;
            if OVERLAP > 0
                WWl(end-p1tmp+1: end-p1tmp+OVERLAP) = sin(linspace(0,pi/2,OVERLAP)').^2 ;
            end
            
        % if both RHS(j) and LHS(j+1) are okay (shorter than Qlen2), adaptive to data
        else
            OVERLAP = (locsf(jj)+p2) - (locsf(jj+1)-p1) + 1 ;
            WWr = ones(p2, 1) ;
            WWr(end-OVERLAP+1:end) = cos(linspace(0,pi/2,OVERLAP)').^2 ;

            WWl = ones(p1, 1) ;
            WWl(1:OVERLAP) = sin(linspace(0,pi/2,OVERLAP)').^2 ;

            %tmpc(end-OVERLAP+1: end) = tmpc(end-OVERLAP+1: end) .* WW ;
            %tmpCHECK(end-OVERLAP+1: end) = tmpCHECK(end-OVERLAP+1: end) .* WW ;
        end

    else %locsf(jj)+p2 <= locsf(jj+1)-p1

        flag2 = [flag2 jj] ;
        WWr = ones(p2, 1) ;        
        WWl = ones(p1, 1) ;

    end


    tmpc(p1+2: end) = tmpc(p1+2: end) .* WWr ;
    tmpCHECK(p1+2: end) = tmpCHECK(p1+2: end) .* WWr ;
    clear WWr ;


    % LHS: if the left bdry gets mixed up
%     if jj > 1 && locsf(jj-1)+p2 > locsf(jj)-p1
%         OVERLAP = (locsf(jj-1)+p2) - (locsf(jj)-p1) + 1 ;
%         Qlen2 = floor((locsf(jj) - locsf(jj-1)) * FACTOR1) ;
%         if p1 > Qlen2 && p2 <= Qlen2 
%             flag = [flag jj] ;
%             p1tmp = Qlen2 ;
%             OVERLAP = (locsf(jj-1)+p2) - (locsf(jj)-p1tmp) + 1 ;
%             WW = zeros(p1, 1) ;
%             WW(end-Qlen2+1:end) = 1 ;
%             if OVERLAP > 0
%                 WW(end-Qlen2+1: end-(Qlen2-OVERLAP)) = sin(linspace(0,pi/2,OVERLAP)').^2 ;
%             end
%             tmpc(1:p1) = tmpc(1:p1) .* WW ;
%             tmpCHECK(1:p1) = tmpCHECK(1:p1) .* WW ;
%         elseif p1 > Qlen2 && p2 > Qlen2
%             flag = [flag jj] ;
%             p2tmp = Qlen2 ;
%             p1tmp = Qlen2 ;
%             OVERLAP = (locsf(jj-1)+p2tmp) - (locsf(jj)-p1tmp) + 1 ;
%             WW = zeros(p1, 1) ;
%             WW(end-Qlen2+1:end) = 1 ;
%             if OVERLAP > 0
%                 WW(end-Qlen2+1: end-(Qlen2-OVERLAP)) = sin(linspace(0,pi/2,OVERLAP)').^2 ;
%             end
%             tmpc(1:p1) = tmpc(1:p1) .* WW ;
%             tmpCHECK(1:p1) = tmpCHECK(1:p1) .* WW ;
%         else
%             WW = zeros(OVERLAP, 1) ;
%             WW(end-OVERLAP+1:end) = sin(linspace(0,pi/2,OVERLAP)').^2 ;
%             tmpc(1:OVERLAP) = tmpc(1:OVERLAP) .* WW ;
%             tmpCHECK(1:OVERLAP) = tmpCHECK(1:OVERLAP) .* WW ;
%         end
%     end

    % determine where to put the (modified) segment
    if locsf(jj)-p1 < 1
        qidx0 = 1: locsf(jj)+p2 ;
        qidx = p-length(qidx0)+1: p ;
    elseif locsf(jj)+p2 > N
        qidx0 = locsf(jj)-p1: N ;
        qidx = 1: p1+N-locsf(jj)+1 ;
    else
        qidx0 = locsf(jj)-p1: locsf(jj)+p2 ;
        qidx = 1: p ;
    end

    % put the (modified) segment
    xq(qidx0) = xq(qidx0) + tmpc(qidx) ;
    CHECK(qidx0) = CHECK(qidx0) + tmpCHECK(qidx) ;

end

% for the final cycle (only need to modify LHS)
tmpc = Y(:, end) ;
tmpCHECK = ones(p, 1) ;

tmpc(1:p1) = tmpc(1:p1) .* WWl ;
tmpCHECK(1:p1) = tmpCHECK(1:p1) .* WWl ;

if locsf(end)+p2 > N
    qidx0 = locsf(end)-p1: N ;
    qidx = 1: p1+N-locsf(end)+1 ;
else
    qidx0 = locsf(end)-p1: locsf(end)+p2 ;
    qidx = 1: p ;
end

% put the (modified) segment
xq(qidx0) = xq(qidx0) + tmpc(qidx) ;
CHECK(qidx0) = CHECK(qidx0) + tmpCHECK(qidx) ;

%figure; plot(CHECK, 'linewidth', 2) ; axis tight ;

if length([flag2])
    %hold on ; plot(locsf(flag2), CHECK(locsf(flag2)),'rx', 'linewidth', 2)
    %keyboard
end

%pause(0.1)