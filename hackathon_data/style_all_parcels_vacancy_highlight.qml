<!DOCTYPE qgis PUBLIC 'http://mrcc.com/qgis.dtd' 'SYSTEM'>
<qgis version="3.34.0" styleCategories="Symbology|Labeling" simplifyDrawingHints="1" simplifyDrawingTol="1" simplifyAlgorithm="0" simplifyLocal="1" simplifyMaxScale="1">
  <renderer-v2 type="RuleRenderer" symbollevels="0" enableorderby="0">
    <rules key="{rules_root}">
      <rule filter="&quot;is_vacant_coded&quot; = 1 AND &quot;is_zero_improvement&quot; = 1" symbol="0" label="Coded Vacant + Zero Improvement" key="{rule_0}"/>
      <rule filter="&quot;is_vacant_coded&quot; = 1 AND &quot;is_zero_improvement&quot; = 0" symbol="1" label="Vacant w/ Improvements" key="{rule_1}"/>
      <rule filter="&quot;is_vacant_coded&quot; = 0 AND &quot;is_zero_improvement&quot; = 1" symbol="2" label="Zero Improvement Only" key="{rule_2}"/>
      <rule filter="ELSE" symbol="3" label="All Other Parcels" key="{rule_3}"/>
    </rules>
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
      <symbol name="1" type="fill" alpha="0.8" clip_to_extent="1" force_rhr="0">
        <layer class="SimpleFill" pass="0" locked="0" enabled="1">
          <prop k="color" v="244,132,95,255"/>
          <prop k="outline_color" v="170,90,65,255"/>
          <prop k="outline_style" v="solid"/>
          <prop k="outline_width" v="0.35"/>
          <prop k="outline_width_unit" v="MM"/>
          <prop k="style" v="solid"/>
        </layer>
      </symbol>
      <symbol name="2" type="fill" alpha="0.8" clip_to_extent="1" force_rhr="0">
        <layer class="SimpleFill" pass="0" locked="0" enabled="1">
          <prop k="color" v="249,199,79,255"/>
          <prop k="outline_color" v="180,140,50,255"/>
          <prop k="outline_style" v="solid"/>
          <prop k="outline_width" v="0.35"/>
          <prop k="outline_width_unit" v="MM"/>
          <prop k="style" v="solid"/>
        </layer>
      </symbol>
      <symbol name="3" type="fill" alpha="0.5" clip_to_extent="1" force_rhr="0">
        <layer class="SimpleFill" pass="0" locked="0" enabled="1">
          <prop k="color" v="232,232,232,255"/>
          <prop k="outline_color" v="180,180,180,255"/>
          <prop k="outline_style" v="solid"/>
          <prop k="outline_width" v="0.1"/>
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
      <rendering scaleMin="0" scaleMax="5000" scaleVisibility="1" obstacle="1" obstacleFactor="1"/>
    </settings>
  </labeling>
</qgis>
