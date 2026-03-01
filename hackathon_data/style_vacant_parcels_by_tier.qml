<!DOCTYPE qgis PUBLIC 'http://mrcc.com/qgis.dtd' 'SYSTEM'>
<qgis version="3.34.0" styleCategories="Symbology|Labeling">
  <renderer-v2 type="categorizedSymbol" attr="vacancy_tier" symbollevels="0" enableorderby="0">
    <categories>
      <category symbol="0" value="Tier 1: Coded Vacant" label="Tier 1: Coded Vacant (19,364)" render="true"/>
      <category symbol="1" value="Tier 2: Zero Improvement" label="Tier 2: Zero Improvement (9,151)" render="true"/>
      <category symbol="2" value="Tier 3: Parking/Abandoned" label="Tier 3: Parking/Abandoned (155)" render="true"/>
    </categories>
    <symbols>
      <symbol name="0" type="fill" alpha="0.85" clip_to_extent="1" force_rhr="0">
        <layer class="SimpleFill" pass="0" locked="0" enabled="1">
          <prop k="color" v="230,57,70,255"/>
          <prop k="outline_color" v="150,30,40,255"/>
          <prop k="outline_style" v="solid"/>
          <prop k="outline_width" v="0.4"/>
          <prop k="outline_width_unit" v="MM"/>
          <prop k="style" v="solid"/>
        </layer>
      </symbol>
      <symbol name="1" type="fill" alpha="0.85" clip_to_extent="1" force_rhr="0">
        <layer class="SimpleFill" pass="0" locked="0" enabled="1">
          <prop k="color" v="255,159,28,255"/>
          <prop k="outline_color" v="180,110,15,255"/>
          <prop k="outline_style" v="solid"/>
          <prop k="outline_width" v="0.4"/>
          <prop k="outline_width_unit" v="MM"/>
          <prop k="style" v="solid"/>
        </layer>
      </symbol>
      <symbol name="2" type="fill" alpha="1" clip_to_extent="1" force_rhr="0">
        <layer class="SimpleFill" pass="0" locked="0" enabled="1">
          <prop k="color" v="106,5,114,255"/>
          <prop k="outline_color" v="60,0,65,255"/>
          <prop k="outline_style" v="solid"/>
          <prop k="outline_width" v="0.8"/>
          <prop k="outline_width_unit" v="MM"/>
          <prop k="style" v="solid"/>
        </layer>
      </symbol>
    </symbols>
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
