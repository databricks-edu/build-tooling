cd output/scorm
rm test.zip
export VERSION=1.0.4
zip -r int-dev-wf-$VERSION.zip *.xsd *.xml
zip -r int-dev-wf-$VERSION.zip html/css html/js/quiz html/js/scorm html/js/launch.js
zip int-dev-wf-$VERSION.zip assessmenttemplate.html launch.html
