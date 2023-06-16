pkg load financial
pkg load matgeom
pkg load statistics
pkg load signal

ahrs_n = ahrs + (90.0/180.0)*pi;
for f=1:length(ahrs_n)
  if ahrs_n(f)>pi
    ahrs_n(f) = ahrs_n(f) - 2*pi;
  end
  if ahrs_n(f)<-pi
    ahrs_n(f) = ahrs_n(f) + 2*pi;
  end
end
figure; title("Compass and DF measurement");
hold on;
#plot (phases(:, 1), "LineWidth", 2, "Color", "#AAFFAA");
#plot (phases(:, 2), "LineWidth", 2, "Color", "#AAAAFF");
#plot (phases(:, 3), "LineWidth", 2, "Color", "#FFAAFF");
plot (ahrs_n*180/pi, "m");
plot (df*180/pi, "b");
hold off;
yticks(-180:10:180);
grid on;
grid minor;
#legend("Error","ch0-ch1", "ch0-ch2", "ch0-ch3",  "Compass sensor", "CoreService ROI azimuth");
legend("Compass sensor", "DF azimuth");
xlabel("Time (samples)");
ylabel("Azimuth (deg)");

figure;
plot (ahrs_n*180/pi, df*180/pi, "m");
xlabel("Compass sensor (deg)");
ylabel("DF Azimuth (deg)");
xticks(-180:20:180);
yticks(-180:20:180);
 daspect ([1 1 1]);
 xlim([-180 180]);
 ylim([-180 180]);
grid on;
title("Angle-angle diagram");
