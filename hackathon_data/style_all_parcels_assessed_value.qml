<!DOCTYPE qgis PUBLIC 'http://mrcc.com/qgis.dtd' 'SYSTEM'>
<qgis version="3.34.0" styleCategories="Symbology|Labeling" simplifyDrawingHints="1" simplifyDrawingTol="1" simplifyAlgorithm="0" simplifyLocal="1" simplifyMaxScale="1">
  <renderer-v2 type="graduatedSymbol" attr="VAL_ASSD" symbollevels="0" graduatedMethod="GraduatedColor" enableorderby="0">
    <ranges>
      <range lower="0" upper="100000" symbol="0" label="&lt; $100K" render="true"/>
      <range lower="100000" upper="250000" symbol="1" label="$100K - $250K" render="true"/>
      <range lower="250000" upper="500000" symbol="2" label="$250K - $500K" render="true"/>
      <range lower="500000" upper="750000" symbol="3" label="$500K - $750K" render="true"/>
      <range lower="750000" upper="1000000" symbol="4" label="$750K - $1M" render="true"/>
      <range lower="1000000" upper="3000000" symbol="5" label="$1M - $3M" render="true"/>
      <range lower="3000000" upper="999999999" symbol="6" label="&gt; $3M" render="true"/>
    </ranges>
    <symbols>
      <!-- YlGnBu ColorBrewer palette (colorblind-safe) -->
      <symbol name="0" type="fill" alpha="0.8" clip_to_extent="1" force_rhr="0">
        <layer class="SimpleFill" pass="0" locked="0" enabled="1">
          <prop k="color" v="255,255,204,255"/>
          <prop k="outline_color" v="200,200,160,255"/>
          <prop k="outline_style" v="solid"/>
          <prop k="outline_width" v="0.1"/>
          <prop k="outline_width_unit" v="MM"/>
          <prop k="style" v="solid"/>
        </layer>
      </symbol>
      <symbol name="1" type="fill" alpha="0.8" clip_to_extent="1" force_rhr="0">
        <layer class="SimpleFill" pass="0" locked="0" enabled="1">
          <prop k="color" v="199,233,180,255"/>
          <prop k="outline_color" v="155,185,140,255"/>
          <prop k="outline_style" v="solid"/>
          <prop k="outline_width" v="0.1"/>
          <prop k="outline_width_unit" v="MM"/>
          <prop k="style" v="solid"/>
        </layer>
      </symbol>
      <symbol name="2" type="fill" alpha="0.8" clip_to_extent="1" force_rhr="0">
        <layer class="SimpleFill" pass="0" locked="0" enabled="1">
          <prop k="color" v="127,205,187,255"/>
          <prop k="outline_color" v="90,150,135,255"/>
          <prop k="outline_style" v="solid"/>
          <prop k="outline_width" v="0.1"/>
          <prop k="outline_width_unit" v="MM"/>
          <prop k="style" v="solid"/>
        </layer>
      </symbol>
      <symbol name="3" type="fill" alpha="0.8" clip_to_extent="1" force_rhr="0">
        <layer class="SimpleFill" pass="0" locked="0" enabled="1">
          <prop k="color" v="65,182,196,255"/>
          <prop k="outline_color" v="45,130,140,255"/>
          <prop k="outline_style" v="solid"/>
          <prop k="outline_width" v="0.1"/>
          <prop k="outline_width_unit" v="MM"/>
          <prop k="style" v="solid"/>
        </layer>
      </symbol>
      <symbol name="4" type="fill" alpha="0.8" clip_to_extent="1" force_rhr="0">
        <layer class="SimpleFill" pass="0" locked="0" enabled="1">
          <prop k="color" v="29,145,192,255"/>
          <prop k="outline_color" v="20,100,135,255"/>
          <prop k="outline_style" v="solid"/>
          <prop k="outline_width" v="0.1"/>
          <prop k="outline_width_unit" v="MM"/>
          <prop k="style" v="solid"/>
        </layer>
      </symbol>
      <symbol name="5" type="fill" alpha="0.8" clip_to_extent="1" force_rhr="0">
        <layer class="SimpleFill" pass="0" locked="0" enabled="1">
          <prop k="color" v="34,94,168,255"/>
          <prop k="outline_color" v="22,65,118,255"/>
          <prop k="outline_style" v="solid"/>
          <prop k="outline_width" v="0.1"/>
          <prop k="outline_width_unit" v="MM"/>
          <prop k="style" v="solid"/>
        </layer>
      </symbol>
      <symbol name="6" type="fill" alpha="0.85" clip_to_extent="1" force_rhr="0">
        <layer class="SimpleFill" pass="0" locked="0" enabled="1">
          <prop k="color" v="12,44,132,255"/>
          <prop k="outline_color" v="8,30,90,255"/>
          <prop k="outline_style" v="solid"/>
          <prop k="outline_width" v="0.1"/>
          <prop k="outline_width_unit" v="MM"/>
          <prop k="style" v="solid"/>
        </layer>
      </symbol>
    </symbols>
    <mode name="Custom"/>
  </renderer-v2>
  <labeling type="simple">
    <settings calloutType="simple">
      <text-style fieldName="SITE_ADDR" fontSize="8" fontFamily="Sans Serif" textColor="40,40,40,255" textOpacity="1">
        <text-buffer bufferDraw="1" bufferSize="0.8" bufferColor="255,255,255,210" bufferSizeUnits="MM"/>
      </text-style>
      <text-format wrapChar="" autoWrapLength="0"/>
      <placement placement="1" priority="5" centroidInside="1"/>
      <rendering scaleMin="0" scaleMax="5000" scaleVisibility="1" obstacle="1" obstacleFactor="1"/>
    </settings>
  </labeling>
</qgis>
