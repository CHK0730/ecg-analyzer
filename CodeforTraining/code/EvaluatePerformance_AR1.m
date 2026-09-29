function [Metrics] = EvaluatePerformance_AR1(x,EST,locsf,Fs)
[~, d] = size(EST) ;
n = length(locsf);
AR = zeros(n, d) ;
L = 30; % 30 cycles left and right for isoelectric point
for ll = 1: n
    %ll
    if ll <L+1
        left = 1; right = 2*L+1;
    elseif ll+L>n
        left = n-2*L; right = n;
    else
        left = ll-L; right = ll+L;
    end

    % Current 30 cycles
    x_jj = x(locsf(left):locsf(right));
    locsf_ll = locsf(ll)-locsf(left)+1;
    locsf_jj = locsf(left:right)-locsf(left)+1;
    locsf_jj = round(locsf_jj/10);
    locsf_jj(end) = []; locsf_jj(1) = [];
    %Detect Peaks
    position0 = wavedet_3D_pcs(x_jj(1:10:end),locsf_jj,round(Fs/10));
    %P onset
    Pon = position0.Pon;Pon = Pon(~isnan(Pon));Pon = Pon*10;
    % 50 ms
    Pon0 = Pon-round(Fs/20);
    %QRS onset and T offset
    QRSon = position0.QRSon; %QRSon = QRSon(~isnan(QRSon));
    QRSon = QRSon*10;
    Toff = position0.Toff; %Toff = Toff(~isnan(Toff));
    Toff = Toff*10;
    [~,ind_on] = find((locsf_ll-QRSon)>0,1,'last');
    QRSon = QRSon(ind_on)+locsf(left)-1;
    [~,ind_off] = find((locsf_ll-Toff)<0,1,'first');
    Toff = Toff(ind_off)+locsf(left)-1;
    E = [];

    for i = 1:length(Pon)
        tmp = x_jj(Pon0(i):Pon(i)); tmp = tmp - median(tmp);
        E = [E,tmp'];
    end
    for jj = 1: d

        %QRST for ll-th cycle and for jj-th approach
        Ytmp = EST(QRSon:Toff,jj);
        %Compute AR
        A = median(abs(Ytmp - median(Ytmp)));
        B = median(abs(E - median(E)));
        A95 = quantile(abs(Ytmp - median(Ytmp)),.95);
        B95 = quantile(abs(E - median(E)),.95);
        AR(ll,jj) =  log((A/B + B/A)*(A95/B95+B95/A95)/4);
    end


end
Metrics.AR = AR ;
end