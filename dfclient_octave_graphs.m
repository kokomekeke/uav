pkg load financial
pkg load matgeom
pkg load statistics
pkg load signal

index = (1:length(ahrs));
ahrs_n = ahrs + (90.0/180.0)*pi;  # manual angle correction
df_n = df;




for f=1:length(ahrs_n)
  if ahrs_n(f)>pi
    ahrs_n(f) = ahrs_n(f) - 2*pi;
  end
  if ahrs_n(f)<-pi
    ahrs_n(f) = ahrs_n(f) + 2*pi;
  end
end

ahrs_n = ahrs_n(:).'; df_n = df_n(:).'; index = index(:).';
discontinuities = (abs(diff(ahrs_n))>pi | abs(diff(df_n))>pi);
ahrs_n = [ahrs_n; nan(1,length(ahrs_n))];
df_n = [df_n; nan(1,length(df_n))];
index = [index; nan(1,length(index))];
ahrs_n(2*find(~discontinuities)) = [];
df_n(2*find(~discontinuities)) = [];
index(2*find(~discontinuities)) = [];
ahrs_n = ahrs_n(:).'; df_n = df_n(:).'; index = index(:).';

figure; title("Compass and DF measurement");
hold on;
#plot (phases(:, 1), "LineWidth", 2, "Color", "#AAFFAA");
#plot (phases(:, 2), "LineWidth", 2, "Color", "#AAAAFF");
#plot (phases(:, 3), "LineWidth", 2, "Color", "#FFAAFF");
area(abs(angleDiff(rmmissing(ahrs_n), rmmissing(df_n)))*180/pi,'LineStyle','none','FaceColor', '#FFAAAA')
plot (index, ahrs_n*180/pi, "m");
plot (index, df_n*180/pi, "b");
hold off;
yticks(-180:10:180);
grid on;
grid minor;
legend("Error", "Compass sensor", "DF azimuth");
xlabel("Time (samples)");
ylabel("Azimuth (deg)");

figure;
plot (ahrs_n*180/pi, df_n*180/pi, "m");
xlabel("Compass sensor (deg)");
ylabel("DF Azimuth (deg)");
xticks(-180:20:180);
yticks(-180:20:180);
 daspect ([1 1 1]);
 xlim([-180 180]);
 ylim([-180 180]);
grid on;
title("Angle-angle diagram");

adiff = angleDiff(rmmissing(ahrs_n), rmmissing(df_n));
rms_error = rms(adiff*180/pi)
