<!DOCTYPE qgis PUBLIC 'http://mrcc.com/qgis.dtd' 'SYSTEM'>
<qgis version="3.34.0" styleCategories="Symbology|Labeling">
  <renderer-v2 type="RuleRenderer" symbollevels="0" enableorderby="0">
    <rules key="{rules_root}">
      <rule filter="&quot;ASSESSEE_OWNER_NAME_1&quot; ILIKE '%CITY OF%' OR &quot;ASSESSEE_OWNER_NAME_1&quot; ILIKE '%COUNTY OF%' OR &quot;ASSESSEE_OWNER_NAME_1&quot; ILIKE '%STATE OF%' OR &quot;ASSESSEE_OWNER_NAME_1&quot; ILIKE '%UNITED STATES%' OR &quot;ASSESSEE_OWNER_NAME_1&quot; ILIKE '%HOUSING AUTH%' OR &quot;ASSESSEE_OWNER_NAME_1&quot; ILIKE '%SCHOOL DIST%' OR &quot;ASSESSEE_OWNER_NAME_1&quot; ILIKE '%FLOOD CONTROL%' OR &quot;ASSESSEE_OWNER_NAME_1&quot; ILIKE '%WATER DIST%' OR &quot;ASSESSEE_OWNER_NAME_1&quot; ILIKE '%RECLAMATION%' OR &quot;ASSESSEE_OWNER_NAME_1&quot; ILIKE '%FIRE DIST%'" symbol="0" label="Government" key="{rule_0}"/>
      <rule filter="&quot;ASSESSEE_OWNER_NAME_1&quot; ILIKE '%LLC%' OR &quot;ASSESSEE_OWNER_NAME_1&quot; ILIKE '% INC%' OR &quot;ASSESSEE_OWNER_NAME_1&quot; ILIKE '%CORP%' OR &quot;ASSESSEE_OWNER_NAME_1&quot; ILIKE '%TRUST%' OR &quot;ASSESSEE_OWNER_NAME_1&quot; ILIKE '% LP' OR &quot;ASSESSEE_OWNER_NAME_1&quot; ILIKE '%LTD%' OR &quot;ASSESSEE_OWNER_NAME_1&quot; ILIKE '%PARTNERS%' OR &quot;ASSESSEE_OWNER_NAME_1&quot; ILIKE '%COMPANY%' OR &quot;ASSESSEE_OWNER_NAME_1&quot; ILIKE '%ASSOC%'" symbol="1" label="Corporate / LLC / Trust" key="{rule_1}"/>
      <rule filter="ELSE" symbol="2" label="Individual / Other" key="{rule_2}"/>
    </rules>
    <symbols>
      <!-- Government - steel blue -->
      <symbol name="0" type="fill" alpha="0.85" clip_to_extent="1" force_rhr="0">
        <layer class="SimpleFill" pass="0" locked="0" enabled="1">
          <prop k="color" v="69,123,157,255"/>
          <prop k="outline_color" v="45,80,105,255"/>
          <prop k="outline_style" v="solid"/>
          <prop k="outline_width" v="0.4"/>
          <prop k="outline_width_unit" v="MM"/>
          <prop k="style" v="solid"/>
        </layer>
      </symbol>
      <!-- Corporate / LLC / Trust - red -->
      <symbol name="1" type="fill" alpha="0.85" clip_to_extent="1" force_rhr="0">
        <layer class="SimpleFill" pass="0" locked="0" enabled="1">
          <prop k="color" v="230,57,70,255"/>
          <prop k="outline_color" v="150,30,40,255"/>
          <prop k="outline_style" v="solid"/>
          <prop k="outline_width" v="0.4"/>
          <prop k="outline_width_unit" v="MM"/>
          <prop k="style" v="solid"/>
        </layer>
      </symbol>
      <!-- Individual / Other - warm sand -->
      <symbol name="2" type="fill" alpha="0.75" clip_to_extent="1" force_rhr="0">
        <layer class="SimpleFill" pass="0" locked="0" enabled="1">
          <prop k="color" v="244,162,97,255"/>
          <prop k="outline_color" v="175,115,65,255"/>
          <prop k="outline_style" v="solid"/>
          <prop k="outline_width" v="0.26"/>
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
