pkg load financial
pkg load matgeom
pkg load statistics
pkg load signal

roi_azimuth = roi(:, 1);
angles=compass;
adiff = angleDiff(angles, roi_azimuth);
adiff_prev = 0;
for f=1:length(adiff)
  if isfinite(adiff(f))
    adiff(f) = adiff_prev + angleDiff(adiff_prev, adiff(f));
    adiff_prev = adiff(f);
  end
end

angles = angles .+ mean(rmmissing(adiff));
angles = angleDiff(0, angles);


angles_prev = 0;
##for f=1:length(angles)
##  if isfinite(angles(f))
##    angles(f) = angles_prev + angleDiff(angles_prev, angles(f));
##    angles_prev = angles(f);
##  end
##end

adiff = angleDiff(angles, roi_azimuth);
adiff(~isfinite(adiff))=0;
##angles_prev = 0;
##for f=1:length(angles)
##  if isfinite(angles(f))
##    angles(f) = angles_prev + angleDiff(angles_prev, angles(f));
##    angles_prev = angles(f)
##  end
##end
##roi_azimuth_prev = 0;
##for f=1:length(roi_azimuth)
##  if isfinite(roi_azimuth(f))
##    roi_azimuth(f) = roi_azimuth_prev + angleDiff(roi_azimuth_prev, roi_azimuth(f));
##    roi_azimuth_prev = roi_azimuth(f)
##  end
##end
figure; title("Compass and CS measurement");
hold on;
area ( adiff*180/pi ,'LineStyle','none','FaceColor','y');
#plot (phases(:, 1), "LineWidth", 2, "Color", "#AAFFAA");
#plot (phases(:, 2), "LineWidth", 2, "Color", "#AAAAFF");
#plot (phases(:, 3), "LineWidth", 2, "Color", "#FFAAFF");
plot (angles*180/pi, "m");
plot (roi_azimuth*180/pi, "b");
hold off;
yticks(-180:10:180);
grid on;
grid minor;
rms(adiff*180/pi)
#legend("Error","ch0-ch1", "ch0-ch2", "ch0-ch3",  "Compass sensor", "CoreService ROI azimuth");
legend("Error","Compass sensor", "CoreService ROI azimuth");
xlabel("Time (samples)");
ylabel("Azimuth (deg)");

figure;
plot (angles*180/pi, roi_azimuth*180/pi, "m");
xlabel("Compass sensor (deg)");
ylabel("CoreService ROI Azimuth (deg)");
xticks(-180:20:180);
yticks(-180:20:180);
 daspect ([1 1 1]);
 xlim([-180 180]);
 ylim([-180 180]);
grid on;
title("Angle-angle diagram");
