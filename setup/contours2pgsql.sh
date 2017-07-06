#!/bin/bash

# http://www.opendem.info/download_contours.html
# http://opendemdata.info/data/srtm_contour/N00E006.zip

created=0

function process {
    echo "${pck}"
    pck=$1
    zip="${pck}.zip"
    url="http://opendemdata.info/data/srtm_contour/${zip}"
    shp="${pck}/${pck}.shp"
    wget -q $url
    if [ $? -ne 0 ]
    then
	if [ $? -ne 8 ]
	then
	    echo "Failed to fetch ${url}" >&2
	fi
	return
    fi
    unzip -q $zip
    if [ $? -ne 0 ]
    then
	echo "Failed to unzip ${zip}" >&2
	return
    fi
    args=('-D' '-s' '3857' '-W' 'UTF-8' '-g' 'the_geom')
    (( created == 0 )) && args+=( '-d' )
    (( created == 1 )) && args+=( '-a' )
    created=1
    args+=("${shp}" "contours")
    shp2pgsql "${args[@]}" | psql -q gis
    if [ $? -eq 0 ]
    then
	rm -rf ${pck}
	rm -f ${zip}
    else
	echo "Failed to import ${pck}" >&2
    fi
}

for i in {00..90};
do
    for j in {000..180};
    do
	process "N${i}E${j}"
	process "N${i}W${j}"
	process "S${i}E${j}"
	process "S${i}W${j}"
    done
done
