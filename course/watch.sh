if [ `uname` == "Linux" ]
  then
  inotifywait -m -r -q --format '%w' ../md | while read FILE; do
    echo "something happened on path $FILE";
    file=$FILE make html_single
  done
else
  while FILE=`kqwait md/*.md`; do
    echo "something happened on path $FILE";
    file=$FILE make html_single
  done
fi
