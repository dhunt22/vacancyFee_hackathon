<!DOCTYPE qgis PUBLIC 'http://mrcc.com/qgis.dtd' 'SYSTEM'>
<qgis version="3.34.0" styleCategories="Symbology|Labeling">
  <renderer-v2 type="graduatedSymbol" attr="VAL_ASSD_LAND" symbollevels="0" graduatedMethod="GraduatedColor" enableorderby="0">
    <ranges>
      <range lower="0" upper="10000" symbol="0" label="&lt; $10K" render="true"/>
      <range lower="10000" upper="50000" symbol="1" label="$10K - $50K" render="true"/>
      <range lower="50000" upper="100000" symbol="2" label="$50K - $100K" render="true"/>
      <range lower="100000" upper="250000" symbol="3" label="$100K - $250K" render="true"/>
      <range lower="250000" upper="500000" symbol="4" label="$250K - $500K" render="true"/>
      <range lower="500000" upper="999999999" symbol="5" label="&gt; $500K" render="true"/>
    </ranges>
    <symbols>
      <symbol name="0" type="fill" alpha="0.85" clip_to_extent="1" force_rhr="0">
        <layer class="SimpleFill" pass="0" locked="0" enabled="1">
          <prop k="color" v="255,247,236,255"/>
          <prop k="outline_color" v="200,195,185,255"/>
          <prop k="outline_style" v="solid"/>
          <prop k="outline_width" v="0.26"/>
          <prop k="outline_width_unit" v="MM"/>
          <prop k="style" v="solid"/>
        </layer>
      </symbol>
      <symbol name="1" type="fill" alpha="0.85" clip_to_extent="1" force_rhr="0">
        <layer class="SimpleFill" pass="0" locked="0" enabled="1">
          <prop k="color" v="254,232,200,255"/>
          <prop k="outline_color" v="200,180,155,255"/>
          <prop k="outline_style" v="solid"/>
          <prop k="outline_width" v="0.26"/>
          <prop k="outline_width_unit" v="MM"/>
          <prop k="style" v="solid"/>
        </layer>
      </symbol>
      <symbol name="2" type="fill" alpha="0.85" clip_to_extent="1" force_rhr="0">
        <layer class="SimpleFill" pass="0" locked="0" enabled="1">
          <prop k="color" v="253,212,158,255"/>
          <prop k="outline_color" v="200,165,120,255"/>
          <prop k="outline_style" v="solid"/>
          <prop k="outline_width" v="0.26"/>
          <prop k="outline_width_unit" v="MM"/>
          <prop k="style" v="solid"/>
        </layer>
      </symbol>
      <symbol name="3" type="fill" alpha="0.85" clip_to_extent="1" force_rhr="0">
        <layer class="SimpleFill" pass="0" locked="0" enabled="1">
          <prop k="color" v="252,141,89,255"/>
          <prop k="outline_color" v="180,100,60,255"/>
          <prop k="outline_style" v="solid"/>
          <prop k="outline_width" v="0.26"/>
          <prop k="outline_width_unit" v="MM"/>
          <prop k="style" v="solid"/>
        </layer>
      </symbol>
      <symbol name="4" type="fill" alpha="0.85" clip_to_extent="1" force_rhr="0">
        <layer class="SimpleFill" pass="0" locked="0" enabled="1">
          <prop k="color" v="227,74,51,255"/>
          <prop k="outline_color" v="160,50,35,255"/>
          <prop k="outline_style" v="solid"/>
          <prop k="outline_width" v="0.26"/>
          <prop k="outline_width_unit" v="MM"/>
          <prop k="style" v="solid"/>
        </layer>
      </symbol>
      <symbol name="5" type="fill" alpha="0.85" clip_to_extent="1" force_rhr="0">
        <layer class="SimpleFill" pass="0" locked="0" enabled="1">
          <prop k="color" v="179,0,0,255"/>
          <prop k="outline_color" v="120,0,0,255"/>
          <prop k="outline_style" v="solid"/>
          <prop k="outline_width" v="0.26"/>
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
      <rendering scaleMin="0" scaleMax="10000" scaleVisibility="1" obstacle="1" obstacleFactor="1"/>
    </settings>
  </labeling>
</qgis>
